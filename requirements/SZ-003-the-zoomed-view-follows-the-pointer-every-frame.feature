@invariant @shell
Feature: SZ-003 The zoomed view follows the pointer every frame
  While zoomed, the view moves with the pointer in step with the display: each frame drawn
  while the pointer moves shows the view where the pointer is, not where a slower timer
  last saw it. The test screen refreshes at 144 Hz, where GNOME's own pointer timer would
  move the view 60 times a second.

  Scenario: Moving the pointer moves the view on almost every frame
    Given zoom is on at 4x
    When the pointer moves 4 pixels every 5 ms for 300 ms
    Then the view moves at least 120 times a second while the pointer moves
