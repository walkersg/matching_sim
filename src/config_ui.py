"""Researcher configuration UI: edit ExperimentConfig before running a session."""
from __future__ import annotations
import pygame
import pygame._freetype as _ft
from typing import Optional

from .config import ExperimentConfig, SchedulePair
from .display import W, H, BLACK, WHITE, GRAY, DGRAY, LTGRAY, BLUE, GREEN, RED, YELLOW, ORANGE

FIELD_H = 32
FIELD_PAD = 6
ROW_H = 36


class _TextField:
    def __init__(self, rect: pygame.Rect, value: str, label: str = "") -> None:
        self.rect = rect
        self.value = value
        self.label = label
        self.active = False
        self._ftf = _ft.Font(None, 18)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True if value changed."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if self.active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
                return True
            elif event.key in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                self.active = False
            elif event.unicode.isprintable():
                self.value += event.unicode
                return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        border_color = WHITE if self.active else DGRAY
        pygame.draw.rect(screen, DGRAY, self.rect)
        pygame.draw.rect(screen, border_color, self.rect, 2, border_radius=4)
        surf, _ = self._ftf.render(self.value, WHITE)
        screen.blit(surf, (self.rect.x + 6, self.rect.y + 7))
        if self.label:
            lbl, _ = self._ftf.render(self.label, GRAY)
            screen.blit(lbl, (self.rect.x - lbl.get_width() - 8, self.rect.y + 7))


class ConfigUI:
    """Simple form-based config editor. Returns updated config or None if cancelled."""

    def __init__(self, screen: pygame.Surface, config: ExperimentConfig) -> None:
        self.screen = screen
        self.config = config
        _ft.init()
        self._ftf_lg = _ft.Font(None, 28)
        self._ftf_lg.strong = True
        self._ftf_md = _ft.Font(None, 20)
        self._ftf_sm = _ft.Font(None, 16)
        self._scroll = 0
        self._fields: dict[str, _TextField] = {}
        self._schedule_fields: list[dict[str, _TextField]] = []
        self._build_fields()

    def _build_fields(self) -> None:
        c = self.config
        x0 = 200
        w = 160

        def tf(key: str, val: str, y: int, label: str) -> _TextField:
            f = _TextField(pygame.Rect(x0, y + 4, w, FIELD_H), val, label)
            self._fields[key] = f
            return f

        tf("cod_ms",                  str(c.cod_ms),                  100, "COD (ms)")
        tf("acquisition_ri_s",        str(c.acquisition_ri_s),        140, "Acquisition RI (s)")
        tf("acquisition_duration_s",  str(c.acquisition_duration_s),  180, "Acquisition duration (s)")
        tf("extinction_duration_s",   str(c.extinction_duration_s),   220, "Extinction duration (s)")
        tf("blackout_ms",             str(c.blackout_ms),             260, "Blackout (ms)")
        tf("break_positions",         ",".join(str(b) for b in c.break_positions), 300, "Break after schedules (csv)")
        tf("break_minimum_ms",        str(c.break_minimum_ms),        340, "Break minimum (ms)")

        # Modality toggle — stored separately
        self._modality = c.modality  # "keyboard" | "mouse"

        # Schedule table
        self._schedule_fields = []
        for sp in c.experimental_schedules:
            self._add_schedule_row(sp)

    def _add_schedule_row(self, sp: Optional[SchedulePair] = None) -> None:
        idx = len(self._schedule_fields)
        base_y = 460 + idx * ROW_H - self._scroll
        ri1 = str(sp.ri1_s) if sp else "1.0"
        ri2 = str(sp.ri2_s) if sp else "1.0"
        dur = str(sp.duration_s) if sp else "200.0"
        row = {
            "ri1": _TextField(pygame.Rect(80,  base_y, 100, FIELD_H), ri1),
            "ri2": _TextField(pygame.Rect(190, base_y, 100, FIELD_H), ri2),
            "dur": _TextField(pygame.Rect(300, base_y, 100, FIELD_H), dur),
        }
        self._schedule_fields.append(row)

    def _rebuild_schedule_rects(self) -> None:
        for idx, row in enumerate(self._schedule_fields):
            base_y = 460 + idx * ROW_H - self._scroll
            row["ri1"].rect.y = base_y + 4
            row["ri2"].rect.y = base_y + 4
            row["dur"].rect.y = base_y + 4

    def run(self) -> Optional[ExperimentConfig]:
        """Blocking call. Returns updated config or None if user pressed Escape."""
        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return None
                    if event.key == pygame.K_RETURN and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        return self._build_config()
                if event.type == pygame.MOUSEWHEEL:
                    self._scroll = max(0, self._scroll - event.y * 20)
                    self._rebuild_schedule_rects()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)

                for f in self._fields.values():
                    f.handle_event(event)
                for row in self._schedule_fields:
                    for f in row.values():
                        f.handle_event(event)

            self._draw()
            pygame.display.flip()
            clock.tick(30)

    def _handle_click(self, pos: tuple[int, int]) -> None:
        # Modality toggle button
        if self._modality_rect.collidepoint(pos):
            self._modality = "mouse" if self._modality == "keyboard" else "keyboard"
        # Add schedule row
        if self._add_row_rect.collidepoint(pos):
            self._add_schedule_row()
            self._rebuild_schedule_rects()
        # Remove last row
        if self._del_row_rect.collidepoint(pos) and len(self._schedule_fields) > 1:
            self._schedule_fields.pop()
        # Save button
        if self._save_rect.collidepoint(pos):
            return  # handled via SHIFT+ENTER; button is visual

    def _draw(self) -> None:
        self.screen.fill((20, 20, 30))
        self._draw_header()
        self._draw_fields()
        self._draw_schedule_table()
        self._draw_buttons()

    def _r(self, ftf, text, color):
        """Render with freetype, returning a Surface."""
        surf, _ = ftf.render(text, color)
        return surf

    def _draw_header(self) -> None:
        lbl = self._r(self._ftf_lg, "Experiment Configuration", WHITE)
        self.screen.blit(lbl, (W // 2 - lbl.get_width() // 2, 20))
        hint = self._r(self._ftf_sm, "Shift+Enter to save  |  Escape to cancel", GRAY)
        self.screen.blit(hint, (W // 2 - hint.get_width() // 2, 58))

    def _draw_fields(self) -> None:
        for f in self._fields.values():
            f.draw(self.screen)

        # Modality
        self._modality_rect = pygame.Rect(200, 388, 160, FIELD_H)
        color = BLUE if self._modality == "keyboard" else YELLOW
        pygame.draw.rect(self.screen, color, self._modality_rect, border_radius=6)
        lbl = self._r(self._ftf_sm, f"Modality: {self._modality}", BLACK)
        self.screen.blit(lbl, (self._modality_rect.x + 8, self._modality_rect.y + 8))
        ml = self._r(self._ftf_sm, "Modality", GRAY)
        self.screen.blit(ml, (self._modality_rect.x - ml.get_width() - 8, self._modality_rect.y + 8))

    def _draw_schedule_table(self) -> None:
        y0 = 430 - self._scroll
        hdr = self._r(self._ftf_sm, "  #    RI 1 (s)    RI 2 (s)    Duration (s)", LTGRAY)
        self.screen.blit(hdr, (40, y0))

        for idx, row in enumerate(self._schedule_fields):
            iy = 460 + idx * ROW_H - self._scroll
            if iy < 60 or iy > H - 60:
                continue
            num = self._r(self._ftf_sm, str(idx + 1), GRAY)
            self.screen.blit(num, (50, iy + 8))
            for f in row.values():
                f.draw(self.screen)

    def _draw_buttons(self) -> None:
        bw, bh = 140, 32
        by = H - 50

        self._add_row_rect = pygame.Rect(W // 2 - bw - 10, by, bw, bh)
        self._del_row_rect = pygame.Rect(W // 2 + 10, by, bw, bh)
        self._save_rect    = pygame.Rect(W - 160, by, 140, bh)

        pygame.draw.rect(self.screen, DGRAY, self._add_row_rect, border_radius=6)
        pygame.draw.rect(self.screen, DGRAY, self._del_row_rect, border_radius=6)
        pygame.draw.rect(self.screen, GREEN, self._save_rect, border_radius=6)

        self.screen.blit(self._r(self._ftf_sm, "+ Add schedule", WHITE),
                         (self._add_row_rect.x + 8, self._add_row_rect.y + 8))
        self.screen.blit(self._r(self._ftf_sm, "– Remove last", WHITE),
                         (self._del_row_rect.x + 8, self._del_row_rect.y + 8))
        self.screen.blit(self._r(self._ftf_sm, "Save (Shift+Enter)", BLACK),
                         (self._save_rect.x + 8, self._save_rect.y + 8))

    def _build_config(self) -> ExperimentConfig:
        c = self.config
        def _int(key: str, default: int) -> int:
            try: return int(self._fields[key].value)
            except ValueError: return default
        def _float(key: str, default: float) -> float:
            try: return float(self._fields[key].value)
            except ValueError: return default

        schedules = []
        for row in self._schedule_fields:
            try:
                ri1 = float(row["ri1"].value)
                ri2 = float(row["ri2"].value)
                dur = float(row["dur"].value)
                schedules.append(SchedulePair(ri1, ri2, dur))
            except ValueError:
                pass

        break_raw = self._fields["break_positions"].value.strip()
        break_positions = []
        if break_raw:
            for tok in break_raw.split(","):
                try: break_positions.append(int(tok.strip()))
                except ValueError: pass

        return ExperimentConfig(
            version=c.version,
            modality=self._modality,
            cod_ms=_int("cod_ms", 500),
            acquisition_ri_s=_float("acquisition_ri_s", 0.7),
            acquisition_duration_s=_float("acquisition_duration_s", 60.0),
            extinction_duration_s=_float("extinction_duration_s", 30.0),
            experimental_schedules=schedules if schedules else c.experimental_schedules,
            blackout_ms=_int("blackout_ms", 5000),
            blackout_after_acquisition=c.blackout_after_acquisition,
            blackout_after_extinction=c.blackout_after_extinction,
            break_positions=break_positions,
            break_minimum_ms=_int("break_minimum_ms", 30000),
            break_maximum_ms=c.break_maximum_ms,
            forced_choice=c.forced_choice,
            forced_choice_extension_s=c.forced_choice_extension_s,
            leaderboard_visible=c.leaderboard_visible,
            max_session_duration_s=c.max_session_duration_s,
        )
