# -*- coding: utf-8 -*-
"""
배달 정산 로컬 관리자 PySide6 앱의 테마, 색상 팔레트, 전역 스타일시트.
"""
from __future__ import annotations

# ---- 색상 토큰 (Figma 디자인에서 파생) -----------------------
COLOR: dict[str, str] = {
    # 서피스 / 배경
    "bg":               "#F8FAFC",
    "surface":          "#FFFFFF",
    "surface_alt":      "#F8FAFC",
    "border":           "#E2E8F0",
    "border_strong":    "#CBD5E1",

    # 텍스트
    "text":             "#0F172A",
    "text_secondary":   "#475569",
    "text_muted":       "#94A3B8",

    # 주요 색 (파란색)
    "primary":          "#2563EB",
    "primary_hover":    "#1D4ED8",
    "primary_pressed":  "#1E40AF",
    "primary_soft":     "#DBEAFE",

    # 상태 색 (badge 배경 / 텍스트 쌍)
    "info_bg":          "#DBEAFE",   "info_fg":     "#1D4ED8",
    "success_bg":       "#DCFCE7",   "success_fg":  "#15803D",
    "danger_bg":        "#FEE2E2",   "danger_fg":   "#B91C1C",
    "warning_bg":       "#FEF3C7",   "warning_fg":  "#B45309",
    "neutral_bg":       "#F1F5F9",   "neutral_fg":  "#475569",
}

FONT_FAMILY: str = (
    '"Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", '
    '"Noto Sans KR", "Segoe UI", sans-serif'
)

# ---- 전역 스타일시트 --------------------------------------------------
GLOBAL_QSS: str = f"""
* {{
    font-family: {FONT_FAMILY};
    color: {COLOR['text']};
}}

QMainWindow, QWidget#root {{
    background: {COLOR['bg']};
}}

/* ---- Header ------------------------------------------------------- */
QFrame#header {{
    background: {COLOR['surface']};
    border-bottom: 1px solid {COLOR['border']};
}}
QLabel#logoBox {{
    background: {COLOR['primary']};
    color: white;
    border-radius: 6px;
    font-weight: 700;
    font-size: 14px;
    qproperty-alignment: AlignCenter;
}}
QLabel#appTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {COLOR['text']};
}}
QPushButton#headerBackBtn {{
    background: transparent;
    color: {COLOR['text_secondary']};
    border: none;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 18px;
    font-weight: 600;
}}
QPushButton#headerBackBtn:hover {{
    background: {COLOR['neutral_bg']};
    color: {COLOR['text']};
}}
QPushButton#headerBackBtn:disabled {{
    color: {COLOR['border_strong']};
}}

/* ---- Sidebar ------------------------------------------------------ */
QFrame#sidebar {{
    background: {COLOR['surface']};
    border-right: 1px solid {COLOR['border']};
}}
QPushButton#navItem {{
    text-align: left;
    padding: 9px 14px;
    border: none;
    border-radius: 8px;
    color: {COLOR['text_secondary']};
    font-size: 13px;
    background: transparent;
}}
QPushButton#navItem:hover {{
    background: {COLOR['neutral_bg']};
    color: {COLOR['text']};
}}
QPushButton#navItem:checked {{
    background: {COLOR['primary_soft']};
    color: {COLOR['primary_hover']};
    font-weight: 600;
}}

/* ---- Page header -------------------------------------------------- */
QLabel#pageTitle {{
    font-size: 24px;
    font-weight: 700;
    color: {COLOR['text']};
}}
QLabel#pageSubtitle {{
    font-size: 12px;
    color: {COLOR['text_muted']};
}}

/* ---- Card --------------------------------------------------------- */
QFrame#card {{
    background: {COLOR['surface']};
    border: 1px solid {COLOR['border']};
    border-radius: 10px;
}}
QLabel#cardTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {COLOR['text']};
}}
QFrame#statCard {{
    background: {COLOR['surface']};
    border: 1px solid {COLOR['border']};
    border-radius: 10px;
}}
QLabel#statLabel {{
    font-size: 11px;
    color: {COLOR['text_muted']};
}}
QLabel#statValue {{
    font-size: 22px;
    font-weight: 700;
    color: {COLOR['text']};
}}
QLabel#statFoot {{
    font-size: 11px;
    color: {COLOR['text_muted']};
}}
QLabel#statFootInfo  {{ color: {COLOR['info_fg']};    font-size: 11px; }}
QLabel#statFootError {{ color: {COLOR['danger_fg']};  font-size: 11px; }}
QLabel#statFootOk    {{ color: {COLOR['success_fg']}; font-size: 11px; }}

/* ---- Buttons ------------------------------------------------------ */
QPushButton#btnPrimary {{
    background: {COLOR['primary']};
    color: white;
    border: 1px solid {COLOR['primary']};
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btnPrimary:hover  {{ background: {COLOR['primary_hover']}; }}
QPushButton#btnPrimary:pressed{{ background: {COLOR['primary_pressed']}; }}

QPushButton#btnSecondary {{
    background: {COLOR['surface']};
    color: {COLOR['text']};
    border: 1px solid {COLOR['border_strong']};
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btnSecondary:hover {{ background: {COLOR['neutral_bg']}; }}

QPushButton#btnGhost {{
    background: transparent;
    color: {COLOR['text_secondary']};
    border: 1px solid {COLOR['border']};
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
}}
QPushButton#btnGhost:hover {{ background: {COLOR['neutral_bg']}; color: {COLOR['text']}; }}

QPushButton#btnDanger {{
    background: {COLOR['danger_fg']};
    color: white;
    border: 1px solid {COLOR['danger_fg']};
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
}}

/* ---- Inputs ------------------------------------------------------- */
QLineEdit, QDateEdit, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {COLOR['surface']};
    border: 1px solid {COLOR['border_strong']};
    border-radius: 6px;
    padding: 6px 9px;
    font-size: 12px;
    color: {COLOR['text']};
    selection-background-color: {COLOR['primary_soft']};
}}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {COLOR['primary']};
}}
QLabel#fieldLabel {{
    font-size: 11px;
    color: {COLOR['text_muted']};
}}

/* ---- Table -------------------------------------------------------- */
QTableWidget {{
    background: {COLOR['surface']};
    border: none;
    gridline-color: {COLOR['border']};
    font-size: 12px;
    color: {COLOR['text']};
}}
QTableWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {COLOR['border']};
}}
QTableWidget::item:selected {{
    background: {COLOR['primary_soft']};
    color: {COLOR['text']};
}}
QHeaderView::section {{
    background: {COLOR['surface_alt']};
    color: {COLOR['text_muted']};
    border: none;
    border-bottom: 1px solid {COLOR['border']};
    padding: 8px;
    font-size: 11px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background: {COLOR['surface_alt']};
    border: none;
}}

/* ---- Progress bar ------------------------------------------------- */
QProgressBar {{
    background: {COLOR['neutral_bg']};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: right;
    color: {COLOR['text_secondary']};
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: {COLOR['primary']};
    border-radius: 4px;
}}

/* ---- Misc --------------------------------------------------------- */
QLabel#mutedNote {{
    font-size: 12px;
    color: {COLOR['text_muted']};
}}
QLabel#errorNote {{
    font-size: 12px;
    color: {COLOR['danger_fg']};
    font-weight: 600;
}}
QLabel#sectionTitle {{
    font-size: 13px;
    font-weight: 700;
    color: {COLOR['text']};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR['border_strong']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
