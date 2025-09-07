from __future__ import annotations

import threading
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional

from providers.yogonet import YogonetProvider
from providers.salta import SaltaProvider


class Loto5PlusApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Loto 5 Plus Checker")
        self.root.resizable(False, False)
        # Slightly bigger default font and window
        # Set larger default fonts safely (Windows: quote family with space)
        try:
            import tkinter.font as tkfont
            for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
                try:
                    f = tkfont.nametofont(fname)
                    f.configure(family="Segoe UI", size=11)
                except Exception:
                    pass
        except Exception:
            pass
        self.root.minsize(560, 360)

        self.winning_numbers: Optional[List[int]] = None
        self.source_label: str = ""
        self.last_draw_number: Optional[int] = None
        self.last_draw_datetime: Optional[datetime] = None
        self.next_draw_datetime: Optional[datetime] = None

        # UI Layout
        container = tk.Frame(root, padx=12, pady=12)
        container.pack(fill=tk.BOTH, expand=True)

        # Actions
        actions_frame = tk.Frame(container)
        actions_frame.pack(fill=tk.X)

        self.btn_update = tk.Button(
            actions_frame,
            text="Actualizar resultados",
            command=self.update_results,
            width=22,
        )
        self.btn_update.pack(side=tk.LEFT)

        # Winners
        winners_frame = tk.LabelFrame(container, text="Ganadores")
        winners_frame.pack(fill=tk.X, pady=(10, 0))

        top_winners_row = tk.Frame(winners_frame)
        top_winners_row.pack(fill=tk.X, padx=8, pady=(4, 0))
        self.winners_source_var = tk.StringVar(value="Fuente: —")
        tk.Label(top_winners_row, textvariable=self.winners_source_var).pack(side=tk.LEFT)
        self.btn_copy_winners = tk.Button(
            top_winners_row,
            text="Copiar",
            command=self.copy_winners_to_clipboard,
            state=tk.DISABLED,
        )
        self.btn_copy_winners.pack(side=tk.RIGHT)

        meta_row = tk.Frame(winners_frame)
        meta_row.pack(fill=tk.X, padx=8, pady=(0, 0))
        self.draw_num_var = tk.StringVar(value="Sorteo N°: —")
        tk.Label(meta_row, textvariable=self.draw_num_var).pack(side=tk.LEFT)

        times_row = tk.Frame(winners_frame)
        times_row.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.last_draw_var = tk.StringVar(value="Último sorteo: —")
        self.next_draw_var = tk.StringVar(value="Próximo sorteo: —")
        tk.Label(times_row, textvariable=self.last_draw_var).pack(side=tk.LEFT)
        tk.Label(times_row, textvariable=self.next_draw_var).pack(side=tk.RIGHT)

        self.winner_labels: List[tk.Label] = []
        winners_numbers_row = tk.Frame(winners_frame)
        winners_numbers_row.pack(padx=8, pady=6)
        for _ in range(5):
            lbl = tk.Label(
                winners_numbers_row,
                text="—",
                width=4,
                relief=tk.GROOVE,
                borderwidth=1,
                font=("Segoe UI", 14, "bold"),
                padx=6,
                pady=4,
            )
            lbl.pack(side=tk.LEFT, padx=4)
            self.winner_labels.append(lbl)

        # My play
        my_frame = tk.LabelFrame(container, text="Mi jugada")
        my_frame.pack(fill=tk.X, pady=(12, 0))

        entry_row = tk.Frame(my_frame)
        entry_row.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(entry_row, text="Números (0–36, separados por coma):").pack(side=tk.LEFT)
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(entry_row, textvariable=self.entry_var, width=40, font=("Segoe UI", 11))
        self.entry.pack(side=tk.LEFT, padx=(6, 6))
        self.entry.bind("<Return>", lambda _e: self.verify_input())
        self.btn_verify = tk.Button(entry_row, text="Verificar", command=self.verify_input)
        self.btn_verify.pack(side=tk.LEFT)

        # QoL buttons
        qol_row = tk.Frame(my_frame)
        qol_row.pack(fill=tk.X, padx=8)
        self.btn_clear = tk.Button(qol_row, text="Limpiar", command=self.clear_input)
        self.btn_clear.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_paste = tk.Button(qol_row, text="Pegar", command=self.paste_from_clipboard)
        self.btn_paste.pack(side=tk.LEFT)
        self.btn_use_winners = tk.Button(
            qol_row,
            text="Usar ganadores",
            command=self.use_winners_in_entry,
            state=tk.DISABLED,
        )
        self.btn_use_winners.pack(side=tk.RIGHT)

        self.my_labels: List[tk.Label] = []
        my_numbers_row = tk.Frame(my_frame)
        my_numbers_row.pack(padx=8, pady=(0, 8))
        for _ in range(5):
            lbl = tk.Label(
                my_numbers_row,
                text="—",
                width=4,
                relief=tk.GROOVE,
                borderwidth=1,
                font=("Segoe UI", 14, "bold"),
                padx=6,
                pady=4,
            )
            lbl.pack(side=tk.LEFT, padx=4)
            self.my_labels.append(lbl)

        # Store default label background for reset
        self._default_label_bg = self.my_labels[0].cget("bg") if self.my_labels else None

        # Hits counter
        self.hits_var = tk.StringVar(value="Aciertos: —")
        tk.Label(my_frame, textvariable=self.hits_var).pack(anchor="w", padx=8, pady=(0, 6))

        # Status bar
        self.status_var = tk.StringVar(value="Listo")
        status = tk.Label(container, textvariable=self.status_var, anchor="w")
        status.pack(fill=tk.X, pady=(6, 0))

    def update_results(self) -> None:
        # Non-blocking fetch in a background thread
        self.btn_update.config(state=tk.DISABLED, text="Actualizando…")
        self.status_var.set("Descargando último resultado…")

        def worker() -> None:
            # Prefer official/local sources; return first success fast.
            # Enrichment of missing metadata happens in a separate short task.
            from providers.tujugada import TujugadaProvider
            providers = [
                YogonetProvider(),
                TujugadaProvider(),
            ]
            last_error: Optional[str] = None
            for i, p in enumerate(providers):
                try:
                    result = p.fetch()
                    # Immediately show results
                    self.root.after(0, self._on_results_ready, result, None)

                    # If metadata is incomplete, try to enrich quickly without blocking UI
                    def enrich_metadata(index_used: int, base_result) -> None:
                        for j, q in enumerate(providers):
                            if j == index_used:
                                continue
                            try:
                                r2 = q.fetch()
                                changed = False
                                if base_result.last_draw_number is None and r2.last_draw_number is not None:
                                    base_result.last_draw_number = r2.last_draw_number
                                    changed = True
                                if base_result.last_draw_datetime is None and r2.last_draw_datetime is not None:
                                    base_result.last_draw_datetime = r2.last_draw_datetime
                                    changed = True
                                if base_result.next_draw_datetime is None and r2.next_draw_datetime is not None:
                                    base_result.next_draw_datetime = r2.next_draw_datetime
                                    changed = True
                                if changed:
                                    # Update only metadata on UI thread
                                    def apply_update() -> None:
                                        self.last_draw_number = base_result.last_draw_number
                                        self.last_draw_datetime = base_result.last_draw_datetime
                                        self.next_draw_datetime = base_result.next_draw_datetime
                                        self.render_winners()
                                    self.root.after(0, apply_update)
                                    return
                            except Exception:
                                continue

                    if (
                        result.last_draw_number is None
                        or result.last_draw_datetime is None
                        or result.next_draw_datetime is None
                    ):
                        threading.Thread(
                            target=enrich_metadata, args=(i, result), daemon=True
                        ).start()
                    return
                except Exception as e:  # noqa: BLE001
                    last_error = f"{type(e).__name__}: {e}"
                    continue
            self.root.after(0, self._on_results_ready, None, last_error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_results_ready(self, result, error: Optional[str]) -> None:
        # Back on UI thread
        self.btn_update.config(state=tk.NORMAL, text="Actualizar resultados")
        if result is not None and not error:
            # Always sort ascending for display and clipboard
            self.winning_numbers = sorted(result.numbers)
            self.source_label = result.label
            self.last_draw_number = result.last_draw_number
            self.last_draw_datetime = result.last_draw_datetime
            self.next_draw_datetime = result.next_draw_datetime
            self.render_winners()
            self.status_var.set(
                f"Actualizado {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
        else:
            self.status_var.set("Error al actualizar resultados")
            messagebox.showerror(
                "Error",
                "No se pudieron obtener resultados de los proveedores.\n"
                f"Último error: {error or 'desconocido'}",
            )

    def render_winners(self) -> None:
        if not self.winning_numbers:
            self.winners_source_var.set("Fuente: —")
            for lbl in self.winner_labels:
                lbl.config(text="—")
            return
        self.winners_source_var.set(f"Fuente: {self.source_label}")
        for lbl, n in zip(self.winner_labels, self.winning_numbers):
            lbl.config(text=str(n))
        self.btn_copy_winners.config(state=tk.NORMAL)
        self.btn_use_winners.config(state=tk.NORMAL)

        # Draw metadata rendering
        self.draw_num_var.set(
            f"Sorteo N°: {self.last_draw_number}" if self.last_draw_number else "Sorteo N°: —"
        )
        def fmt_dt(dt: Optional[datetime]) -> str:
            return dt.strftime("%d/%m/%Y %H:%M") if dt else "—"
        self.last_draw_var.set(f"Último sorteo: {fmt_dt(self.last_draw_datetime)}")
        self.next_draw_var.set(f"Próximo sorteo: {fmt_dt(self.next_draw_datetime)}")

    def verify_input(self) -> None:
        try:
            nums = self._parse_user_numbers(self.entry_var.get())
        except ValueError as e:
            messagebox.showerror("Entrada inválida", str(e))
            return

        # Show my numbers and color by match
        winners = set(self.winning_numbers or [])
        for lbl, n in zip(self.my_labels, nums):
            lbl.config(text=str(n))
            if n in winners:
                lbl.config(bg="#c7f3d1")  # light green
            else:
                lbl.config(bg="#f8d7da")  # light red

        self.hits_var.set(f"Aciertos: {sum(1 for n in nums if n in winners)} de 5")

        # If no winners loaded yet, inform the user
        if not self.winning_numbers:
            messagebox.showinfo(
                "Sin resultados",
                "Primero actualice los resultados para comparar con el último sorteo.",
            )

    def clear_input(self) -> None:
        self.entry_var.set("")
        self.hits_var.set("Aciertos: —")
        for lbl in self.my_labels:
            lbl.config(text="—")
            if self._default_label_bg is not None:
                lbl.config(bg=self._default_label_bg)

    def paste_from_clipboard(self) -> None:
        try:
            text = self.root.clipboard_get()
        except Exception:
            text = ""
        if text:
            self.entry_var.set(text)
            self.entry.icursor(tk.END)
            self.entry.focus_set()

    def use_winners_in_entry(self) -> None:
        if self.winning_numbers:
            self.entry_var.set(",".join(str(n) for n in self.winning_numbers))
            self.entry.icursor(tk.END)
            self.entry.focus_set()

    def copy_winners_to_clipboard(self) -> None:
        if self.winning_numbers:
            text = ",".join(str(n) for n in self.winning_numbers)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("Ganadores copiados al portapapeles")

    @staticmethod
    def _parse_user_numbers(text: str) -> List[int]:
        # Accept comma, semicolon or whitespace separated
        import re

        parts = [p for p in re.split(r"[\s,;]+", text.strip()) if p]
        if len(parts) != 5:
            raise ValueError("Debe ingresar exactamente 5 números separados por coma.")
        try:
            nums = [int(p) for p in parts]
        except ValueError:
            raise ValueError("Todos los valores deben ser números enteros.")
        if any(n < 0 or n > 36 for n in nums):
            raise ValueError("Los números deben estar en el rango 0–36.")
        if len(set(nums)) != 5:
            raise ValueError("Los 5 números deben ser únicos, sin repetidos.")
        return nums


def main() -> None:
    root = tk.Tk()
    app = Loto5PlusApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
