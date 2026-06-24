"""Pygame display: renders the PRESS-B experiment UI."""
from __future__ import annotations
import math
import pygame
import pygame._freetype as _ft
from typing import Optional

from .session import Phase, ScheduleSession
from .config import ExperimentConfig

# Colors
BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)
GRAY   = (120, 120, 120)
DGRAY  = (50,  50,  50)
GREEN  = (0,   220, 80)
YELLOW = (240, 220, 0)
BLUE   = (60,  120, 240)
RED    = (220, 50,  50)
ORANGE = (240, 140, 0)
LTGRAY = (200, 200, 200)

W, H = 900, 620
FPS  = 60


class _Font:
    """Thin wrapper around pygame._freetype.Font that exposes a pygame.font-like API."""

    def __init__(self, size: int, bold: bool = False) -> None:
        self._f = _ft.Font(None, size)
        if bold:
            self._f.strong = True

    def render(self, text: str, color) -> pygame.Surface:
        """Return a Surface (freetype render returns (surf, rect))."""
        surf, _ = self._f.render(text, color)
        return surf

    def get_rect(self, text: str) -> pygame.Rect:
        return self._f.get_rect(text)


class Display:
    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        pygame.init()
        _ft.init()

        self._audio_ok = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self._audio_ok = True
        except Exception:
            pass

        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("PRESS-B Matching Task")
        self.clock = pygame.time.Clock()
        self._ding = self._make_ding() if self._audio_ok else None

        self._font_lg  = _Font(36, bold=True)
        self._font_md  = _Font(24)
        self._font_sm  = _Font(18)
        self._font_xs  = _Font(14)

        # Flash state: show green for 200ms after reinforcer
        self._flash_until: float = 0.0

        # Cached rects for mouse hit testing
        self._alt1_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._alt2_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    def _make_ding(self):
        import array, math
        rate = 44100
        duration = 0.15
        freq = 880.0
        n = int(rate * duration)
        buf = array.array("h", [0] * n)
        for i in range(n):
            t = i / rate
            envelope = math.exp(-t * 20)
            buf[i] = int(32000 * envelope * math.sin(2 * math.pi * freq * t))
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play_ding(self) -> None:
        if self._ding:
            self._ding.play()
        self._flash_until = pygame.time.get_ticks() + 200

    # ------------------------------------------------------------------
    # Main render dispatch
    # ------------------------------------------------------------------

    def render(self, session: ScheduleSession) -> None:
        self.screen.fill(BLACK)
        phase = session.phase

        if phase == Phase.CONSENT:
            self._draw_consent()
        elif phase == Phase.INSTRUCTIONS:
            self._draw_instructions(session)
        elif phase == Phase.LEADERBOARD:
            self._draw_leaderboard(session)
        elif phase == Phase.BLACKOUT:
            pass  # black screen
        elif phase in (Phase.ACQUISITION, Phase.EXPERIMENTAL, Phase.EXTINCTION):
            self._draw_task(session)
        elif phase == Phase.BREAK:
            self._draw_break(session)
        elif phase == Phase.DEBRIEF:
            self._draw_debrief(session)
        elif phase == Phase.DONE:
            self._draw_done()

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Screen: Consent
    # ------------------------------------------------------------------

    def _draw_consent(self) -> None:
        self._center_text("PRESS-B Matching Task", self._font_lg, WHITE, H // 3)
        lines = [
            "This study records your button presses during a simple computer task.",
            "No personal information beyond a participant ID will be collected.",
            "You may stop at any time.",
            "",
            "Press ENTER to continue.",
        ]
        y = H // 3 + 60
        for line in lines:
            self._center_text(line, self._font_sm, LTGRAY, y)
            y += 28

    # ------------------------------------------------------------------
    # Screen: Instructions
    # ------------------------------------------------------------------

    def _draw_instructions(self, session: ScheduleSession) -> None:
        self._center_text("Instructions", self._font_lg, WHITE, 60)
        modality = session.config.modality
        if modality == "keyboard":
            lines = [
                "Press SPACEBAR to respond on the active key.",
                "Press LEFT CTRL to switch to the other key.",
                "",
                "The active key is shown by the button color:",
                "  BLUE = Alternative 1    YELLOW = Alternative 2",
                "",
                "A green flash and a tone mean you earned a point.",
                "The counter at the bottom tracks your total points.",
                "",
                "Try to earn as many points as possible!",
                "",
                "Press ENTER to begin.",
            ]
        else:
            lines = [
                "Click the LEFT panel to respond on Alternative 1.",
                "Click the RIGHT panel to respond on Alternative 2.",
                "Clicking the inactive panel switches alternatives.",
                "",
                "A green flash and a tone mean you earned a point.",
                "The counter at the bottom tracks your total points.",
                "",
                "Try to earn as many points as possible!",
                "",
                "Press ENTER to begin.",
            ]
        y = 130
        for line in lines:
            self._center_text(line, self._font_sm, LTGRAY, y)
            y += 30

    # ------------------------------------------------------------------
    # Screen: Leaderboard (pre-task)
    # ------------------------------------------------------------------

    def _draw_leaderboard(self, session: ScheduleSession) -> None:
        self._center_text("Leaderboard", self._font_lg, WHITE, 80)
        self._center_text("(Scores from previous participants will appear here.)", self._font_sm, GRAY, 140)
        self._center_text("Press ENTER to start the task.", self._font_md, LTGRAY, H - 80)

    # ------------------------------------------------------------------
    # Screen: Task (acquisition / experimental / extinction)
    # ------------------------------------------------------------------

    def _draw_task(self, session: ScheduleSession) -> None:
        self._draw_schedule_lights(session)

        if session.config.modality == "keyboard":
            self._draw_keyboard_panel(session)
        else:
            self._draw_mouse_panel(session)

        if session.config.leaderboard_visible:
            self._draw_counter(session)

        lbl = self._font_xs.render(session.phase.name.capitalize(), DGRAY)
        self.screen.blit(lbl, (10, H - 20))

    # 9 discriminative stimulus lights across the top; exactly 1 lit during experimental
    def _draw_schedule_lights(self, session: ScheduleSession) -> None:
        n_lights = 9
        light_r = 14
        top_y = 30
        spacing = W // (n_lights + 1)

        pos = session.current_experimental_position
        n_exp = session.n_experimental_schedules

        lit_idx = -1
        if pos > 0 and n_exp > 0:
            lit_idx = round(1 + (pos - 1) * (n_lights - 1) / max(n_exp - 1, 1))

        for i in range(1, n_lights + 1):
            cx = i * spacing
            if i == lit_idx:
                pygame.draw.circle(self.screen, YELLOW, (cx, top_y), light_r)
            else:
                pygame.draw.circle(self.screen, DGRAY, (cx, top_y), light_r)
                pygame.draw.circle(self.screen, GRAY, (cx, top_y), light_r, 1)

    # ------------------------------------------------------------------
    # Keyboard modality panel
    # ------------------------------------------------------------------

    def _draw_keyboard_panel(self, session: ScheduleSession) -> None:
        cx, cy = W // 2, H // 2 + 20

        btn_r = 90
        color = BLUE if session.active_alt == 1 else YELLOW
        if pygame.time.get_ticks() < self._flash_until:
            color = GREEN
        pygame.draw.circle(self.screen, color, (cx, cy), btn_r)
        pygame.draw.circle(self.screen, WHITE, (cx, cy), btn_r, 3)

        label = "COD..." if session.cod_active else "SPACE"
        lbl = self._font_md.render(label, BLACK)
        self.screen.blit(lbl, lbl.get_rect(center=(cx, cy)))

        alt_lbl = self._font_sm.render(f"Alt {session.active_alt}", LTGRAY)
        self.screen.blit(alt_lbl, alt_lbl.get_rect(center=(cx, cy + btn_r + 22)))

        # Changeover button
        co_x, co_y = cx, cy + btn_r + 72
        co_r = 28
        co_color = RED if session.cod_active else ORANGE
        pygame.draw.circle(self.screen, co_color, (co_x, co_y), co_r)
        pygame.draw.circle(self.screen, WHITE, (co_x, co_y), co_r, 2)
        co_lbl = self._font_xs.render("CTRL", BLACK)
        self.screen.blit(co_lbl, co_lbl.get_rect(center=(co_x, co_y)))

        self._draw_ri_info(session, cx, 70)
        self._draw_response_counts(session)

    # ------------------------------------------------------------------
    # Mouse modality panel (two-key design)
    # ------------------------------------------------------------------

    def _draw_mouse_panel(self, session: ScheduleSession) -> None:
        pad = 60
        pw = (W - pad * 3) // 2
        ph = 280
        top = 100

        r1 = pygame.Rect(pad, top, pw, ph)
        r2 = pygame.Rect(pad * 2 + pw, top, pw, ph)
        self._alt1_rect = r1
        self._alt2_rect = r2

        flashing = pygame.time.get_ticks() < self._flash_until
        c1 = GREEN if (flashing and session.active_alt == 1) else (BLUE if session.active_alt == 1 else DGRAY)
        c2 = GREEN if (flashing and session.active_alt == 2) else (YELLOW if session.active_alt == 2 else DGRAY)

        pygame.draw.rect(self.screen, c1, r1, border_radius=18)
        pygame.draw.rect(self.screen, WHITE, r1, 3, border_radius=18)
        pygame.draw.rect(self.screen, c2, r2, border_radius=18)
        pygame.draw.rect(self.screen, WHITE, r2, 3, border_radius=18)

        c_lbl1 = WHITE if session.active_alt == 1 else GRAY
        c_lbl2 = WHITE if session.active_alt == 2 else GRAY
        lbl1 = self._font_md.render("Alt 1", c_lbl1)
        lbl2 = self._font_md.render("Alt 2", c_lbl2)
        self.screen.blit(lbl1, lbl1.get_rect(center=r1.center))
        self.screen.blit(lbl2, lbl2.get_rect(center=r2.center))

        if session.cod_active:
            cod_lbl = self._font_sm.render("COD active", RED)
            self.screen.blit(cod_lbl, cod_lbl.get_rect(center=(W // 2, top + ph + 30)))

        self._draw_ri_info(session, W // 2, 70)
        self._draw_response_counts(session)

    def get_alt1_rect(self) -> pygame.Rect:
        return self._alt1_rect

    def get_alt2_rect(self) -> pygame.Rect:
        return self._alt2_rect

    def _draw_ri_info(self, session: ScheduleSession, cx: int, y: int) -> None:
        if session.phase == Phase.EXTINCTION:
            lbl = self._font_xs.render("Extinction (no reinforcers)", GRAY)
        else:
            lbl = self._font_xs.render(f"RI1={session.ri1_s:.1f}s   RI2={session.ri2_s:.1f}s", DGRAY)
        self.screen.blit(lbl, lbl.get_rect(midtop=(cx, y)))

    def _draw_response_counts(self, session: ScheduleSession) -> None:
        txt = f"B1={session.B1}  B2={session.B2}  R1={session.R1}  R2={session.R2}  CO={session.CO}"
        lbl = self._font_xs.render(txt, GRAY)
        self.screen.blit(lbl, lbl.get_rect(midtop=(W // 2, H - 52)))

    def _draw_counter(self, session: ScheduleSession) -> None:
        lbl = self._font_md.render(f"Points: {session.total_reinforcers}", WHITE)
        self.screen.blit(lbl, lbl.get_rect(midtop=(W // 2, H - 34)))

    # ------------------------------------------------------------------
    # Screen: Break
    # ------------------------------------------------------------------

    def _draw_break(self, session: ScheduleSession) -> None:
        self._center_text("Break", self._font_lg, WHITE, H // 3)
        remaining = max(0.0, session.break_minimum_s - session.break_elapsed_s)
        if remaining > 0:
            msg = f"Please wait {remaining:.0f}s before continuing."
        else:
            msg = "Press ENTER to continue."
        self._center_text(msg, self._font_md, LTGRAY, H // 3 + 70)

    # ------------------------------------------------------------------
    # Screen: Debrief
    # ------------------------------------------------------------------

    def _draw_debrief(self, session: ScheduleSession) -> None:
        self._center_text("Task Complete!", self._font_lg, GREEN, H // 3)
        self._center_text(f"You earned {session.total_reinforcers} points total.", self._font_md, WHITE, H // 3 + 60)
        self._center_text("Thank you for participating.", self._font_sm, LTGRAY, H // 3 + 100)
        self._center_text("Press ENTER to save data and finish.", self._font_sm, LTGRAY, H // 3 + 140)

    # ------------------------------------------------------------------
    # Screen: Done
    # ------------------------------------------------------------------

    def _draw_done(self) -> None:
        self._center_text("Data saved. You may close this window.", self._font_md, LTGRAY, H // 2)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _center_text(self, text: str, font: _Font, color, y: int) -> None:
        surf = font.render(text, color)
        self.screen.blit(surf, surf.get_rect(midtop=(W // 2, y)))

    def tick(self) -> None:
        self.clock.tick(FPS)
