"""Entry point: open the Pong window and run the frame loop at 60 FPS.

Run with ``python -m pong``. This is the only module that imports pygame.
"""

import sys

import pygame

from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH

FPS = 60
# Longest step the simulation may take in one frame, so a slow frame cannot
# let the ball pass through a paddle.
MAX_DT = 0.02


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode(
        (PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT), pygame.RESIZABLE
    )
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()

    running = True
    while running:
        # Seconds since the previous frame, capped at MAX_DT. Nothing consumes
        # it yet; the movement step will use it once it exists.
        _dt = min(clock.tick(FPS) / 1000.0, MAX_DT)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((0, 0, 0))
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
