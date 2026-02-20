from dataclasses import dataclass

@dataclass
class Theme:
    name: str
    bg: str
    bg_panel: str
    accent: str
    accent_dim: str
    text: str
    text_dim: str
    green: str
    yellow: str
    red: str
    white: str
    critical_bg: str  # For semantic background when connection is lost


THEMES = {
    "orange": Theme(
        name="orange",
        bg="#000000",
        bg_panel="#0a0a0a",
        accent="#ff8c00",
        accent_dim="#3d2800",
        text="#d4d4d4",
        text_dim="#707070",
        green="#4ec94e",
        yellow="#ffb347",
        red="#ff4444",
        white="#f0f0f0",
        critical_bg="#4a0000",
    ),
    "matrix": Theme(
        name="matrix",
        bg="#000000",
        bg_panel="#050a05",
        accent="#00ff41",
        accent_dim="#004a11",
        text="#00ea30",
        text_dim="#008a1c",
        green="#00ff41",
        yellow="#b0f21d",
        red="#ff2121",
        white="#e0ffe6",
        critical_bg="#3a0000",
    ),
    "minimal": Theme(
        name="minimal",
        bg="#121212",
        bg_panel="#1e1e1e",
        accent="#ffffff",
        accent_dim="#555555",
        text="#e0e0e0",
        text_dim="#888888",
        green="#81c784",
        yellow="#ffd54f",
        red="#e57373",
        white="#ffffff",
        critical_bg="#3e2723",
    ),
    "monochrome": Theme(
        name="monochrome",
        bg="#000000",
        bg_panel="#000000",
        accent="#ffffff",
        accent_dim="#777777",
        text="#cccccc",
        text_dim="#555555",
        green="#ffffff",
        yellow="#aaaaaa",
        red="#ffffff",
        white="#ffffff",
        critical_bg="#333333",
    ),
    "purple": Theme(
        name="purple",
        bg="#0a0b10",
        bg_panel="#13151f",
        accent="#d4af37",
        accent_dim="#4a3a11",
        text="#e2e2e2",
        text_dim="#6a6c75",
        green="#10b981",
        yellow="#f59e0b",
        red="#e11d48",
        white="#ffffff",
        critical_bg="#3d141e",
    ),
}

def get_theme(name: str) -> Theme:
    """Returns the theme by name, defaults to 'orange' if not found."""
    return THEMES.get(name.lower(), THEMES["orange"])
