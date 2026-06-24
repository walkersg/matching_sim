#!/usr/bin/env python3
"""PRESS-B Matching Task — desktop entry point.

Usage:
  python main.py                         # run with default config
  python main.py --config config.json    # load saved config
  python main.py --participant P01       # set participant ID
  python main.py --output ./data         # output directory (default: ./data)
  python main.py --configure             # open config editor before running
"""
from __future__ import annotations
import argparse
import os
import sys
import uuid

import pygame

from src.config import ExperimentConfig
from src.session import ScheduleSession, Phase
from src.data import SessionRecorder
from src.display import Display
from src.analysis import fit_gml


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PRESS-B Matching Task")
    p.add_argument("--config",      default=None,    help="Path to config JSON file")
    p.add_argument("--participant",  default=None,    help="Participant ID")
    p.add_argument("--output",       default="data",  help="Output directory for session data")
    p.add_argument("--configure",    action="store_true", help="Open config editor before starting")
    return p.parse_args()


def run_config_editor(screen: pygame.Surface, config: ExperimentConfig) -> ExperimentConfig:
    from src.config_ui import ConfigUI
    editor = ConfigUI(screen, config)
    result = editor.run()
    return result if result is not None else config


def main() -> None:
    args = parse_args()

    # Load config
    if args.config and os.path.exists(args.config):
        config = ExperimentConfig.from_file(args.config)
    else:
        config = ExperimentConfig()

    # Participant ID
    participant_id = args.participant or f"P{uuid.uuid4().hex[:6].upper()}"
    session_id = uuid.uuid4().hex[:12]

    # Init pygame
    pygame.init()
    from src.display import W, H
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("PRESS-B Matching Task")

    # Config editor
    if args.configure:
        config = run_config_editor(screen, config)

    # Recorder and session
    recorder = SessionRecorder(session_id, participant_id, args.output, config.modality)
    session = ScheduleSession(config, recorder)
    display = Display(config)
    display.screen = screen

    running = True
    while running:
        # Tick schedule logic
        session.tick()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            # --- Global escape ---
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                break

            # --- Phase-specific input ---
            phase = session.phase

            if phase == Phase.CONSENT:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    session.acknowledge_consent()

            elif phase == Phase.INSTRUCTIONS:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    session.acknowledge_instructions()

            elif phase == Phase.LEADERBOARD:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    session.acknowledge_leaderboard()

            elif phase in (Phase.ACQUISITION, Phase.EXPERIMENTAL, Phase.EXTINCTION):
                _handle_task_input(event, session, display)

            elif phase == Phase.BREAK:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    session.acknowledge_break()

            elif phase == Phase.DEBRIEF:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    session.phase = Phase.DONE

        # Reinforcer flash / ding is triggered from _handle_task_input

        display.render(session)
        display.tick()

        if session.phase == Phase.DONE:
            # Save data
            recorder.save(config.to_json())
            # GML fit
            fit = fit_gml(recorder.summaries, session_id, participant_id)
            if fit:
                out = os.path.join(args.output, f"{session_id}_gml.txt")
                os.makedirs(args.output, exist_ok=True)
                with open(out, "w") as f:
                    f.write(f"Sensitivity (a): {fit.sensitivity:.4f}\n")
                    f.write(f"Log bias (log b): {fit.log_bias:.4f}\n")
                    f.write(f"R²: {fit.r_squared:.4f}\n")
                    f.write(f"N schedules included: {fit.n}\n")
            # Stay on DONE screen until window closed
            while True:
                for ev in pygame.event.get():
                    if ev.type in (pygame.QUIT,) or (
                        ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE
                    ):
                        pygame.quit()
                        sys.exit(0)
                display.render(session)
                display.tick()

    pygame.quit()


def _handle_task_input(
    event: pygame.event.Event,
    session: ScheduleSession,
    display: Display,
) -> None:
    modality = session.config.modality

    if modality == "keyboard":
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                collected = session.respond()
                if collected:
                    display.play_ding()
            elif event.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                session.changeover()

    elif modality == "mouse":
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            alt1_rect = display.get_alt1_rect()
            alt2_rect = display.get_alt2_rect()

            if alt1_rect.collidepoint(pos):
                if session.active_alt == 1:
                    collected = session.respond()
                    if collected:
                        display.play_ding()
                else:
                    session.changeover()
                    # After changeover, this click also counts as a response on new alt
                    collected = session.respond()
                    if collected:
                        display.play_ding()
            elif alt2_rect.collidepoint(pos):
                if session.active_alt == 2:
                    collected = session.respond()
                    if collected:
                        display.play_ding()
                else:
                    session.changeover()
                    collected = session.respond()
                    if collected:
                        display.play_ding()


if __name__ == "__main__":
    main()
