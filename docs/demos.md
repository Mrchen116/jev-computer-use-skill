# Recorded demonstrations

| Demo | Result | Recording |
| --- | --- | --- |
| Tower Defense Clash · CrazyGames · Level 40 | 13 waves, 450/500 health, three stars | [14:10, original speed](media/tower-defense-clash-level40.mp4) |
| Garden Defenders | Three stars, zero mower use | [2:23, original speed](media/garden-defenders.mp4) |
| Zoho invoice generator | Three items, zero tax, verified USD 440 | [0:59, original speed](media/zoho-invoice.mp4) |

## Tower Defense Clash — commercial game platform

https://github.com/user-attachments/assets/7c9f1aa3-703e-4c44-b1aa-caf1a5dd8572

On [CrazyGames](https://www.crazygames.com/game/tower-defense-clash), Jev chooses
complete builds, upgrades, spell targets and saving actions from live game state.
The outer agent provides a strategy; code computes geometry and approximate action
effects, enforces the declared investment stages, and executes the chosen mouse
controls. This recording clears **level 40**, all **13 waves**, with **450/500
health and three stars**, without an intermediate LLM call or strategy update.

The run took 849.13 seconds and made 243 calls to `jev-1.13.0`, using 2,540,140
input tokens: **$0.10669** at $0.042 per million input tokens. This excludes outer
agent preparation, debugging and review, and earlier attempts. Five spell actions
were canceled because the chosen enemy group had already died; no wrong-location
builds were observed.

The uncut 14:10 recording includes level entry, combat and the victory screen.
It was transcoded to H.264 MP4 without changing speed. The requested guest level
was unlocked during setup; health, money, enemies, cooldowns and game time were
not modified. The strategy has game-specific constraints; one recorded win is
not a stable success-rate or general-gameplay claim.

This uses a game-specific Phaser state reader and Playwright pointer actions.
No visual recognition or default-native-CUA support is implied. The reader uses
current engine state and static geometry, including offscreen areas, rather than
future wave definitions. [Earlier level-1 demo and adapter background](../evals/games/clash.md).

## Garden Defenders — custom game adapter

https://github.com/user-attachments/assets/94e7fcb5-cbee-4383-ac2f-eef69b9584f7

An existing [third-party game](https://seth-xh.github.io/pvz/), played through an
agent-authored adapter using the [custom Skill workflow](../skills/jev-computer-use/references/adapters.md).
The outer agent prepares observations, complete action choices and priorities;
Jev handles the game loop without an intervening LLM. The game is never paused
for inference. This recording starts before the first action and includes the
victory screen. It was transcoded without changing speed or cutting gameplay.

The final recorded run won the three-wave first level with zero mower use. Two
successive development runs achieved zero mower use; random enemy patterns were
not held fixed, so this is a demonstration, not a controlled success-rate claim.
The first experiment also won but used two mowers. The video shows the final
selection-toggle fix. All results, including the failed initial plant attempt in
the preceding development run, are retained in the [sanitized results](../evals/games/pvz-results.json).

[Reproduction and adapter code](../evals/games/README.md).
This game reads JavaScript state and uses Playwright input; it does not demonstrate
vision or the default native CUA backend. Game artwork belongs to its respective
authors; the project supplies the agent adapter, not the game.

## Zoho invoice generator — real business form

https://github.com/user-attachments/assets/2d8004de-8e3c-45e3-b9f4-b8397f276988

On [Zoho's public invoice generator](https://www.zoho.com/invoice/free-invoice-generator.html),
Jev chooses each field and then its prepared literal value. The host supplies the
synthetic invoice and computes the expected total; the worker executes real clicks
and typing. The final run fills 20 fields in 59.50 seconds, with no intermediate
LLM call. All 32 host checks pass: three items, zero tax and USD 440 total.
Nothing is sent or saved online.

This is the custom DOM/Playwright route, not the default native CUA backend.
The uncut recording includes the complete filling run; earlier adapter failures
are retained in the [results and reproduction guide](../evals/forms/zoho.md).
