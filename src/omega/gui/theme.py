"""ttk theme configuration applied only after explicit GUI startup."""

from __future__ import annotations

from tkinter import Tk, ttk


class ThemeManager:
    """Apply readable system, light, or dark ttk styles."""

    def __init__(self, root: Tk) -> None:
        self.root = root
        self.style = ttk.Style(root)

    def apply(self, theme: str, font_size: int) -> dict[str, str]:
        """Apply one validated theme and return text-widget colors."""

        selected = theme if theme in {"system", "light", "dark"} else "system"
        if selected == "dark":
            background = "#202124"
            surface = "#292a2d"
            foreground = "#f1f3f4"
            accent = "#8ab4f8"
            muted = "#bdc1c6"
            self.style.theme_use("clam")
        elif selected == "light":
            background = "#f4f6f8"
            surface = "#ffffff"
            foreground = "#202124"
            accent = "#2457a7"
            muted = "#5f6368"
            self.style.theme_use("clam")
        else:
            background = self.style.lookup("TFrame", "background") or "#f0f0f0"
            surface = self.style.lookup("TEntry", "fieldbackground") or "#ffffff"
            foreground = self.style.lookup("TLabel", "foreground") or "#202124"
            accent = "#2457a7"
            muted = foreground

        base_font = ("Segoe UI", font_size)
        self.root.configure(background=background)
        self.style.configure(".", font=base_font)
        self.style.configure("TFrame", background=background)
        self.style.configure("Surface.TFrame", background=surface)
        self.style.configure(
            "Header.TLabel",
            background=background,
            foreground=foreground,
            font=("Segoe UI Semibold", font_size + 7),
        )
        self.style.configure(
            "State.TLabel",
            background=background,
            foreground=accent,
            font=("Segoe UI Semibold", font_size),
        )
        self.style.configure("TLabel", background=background, foreground=foreground)
        self.style.configure("Muted.TLabel", background=background, foreground=muted)
        self.style.configure("Treeview", rowheight=max(24, font_size * 2))
        self.style.configure(
            "Treeview",
            background=surface,
            fieldbackground=surface,
            foreground=foreground,
        )
        self.style.configure(
            "Treeview.Heading",
            background=background,
            foreground=foreground,
        )
        return {
            "background": background,
            "surface": surface,
            "foreground": foreground,
            "accent": accent,
        }
