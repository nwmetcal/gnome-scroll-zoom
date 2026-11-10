@invariant @shell
Feature: SZ-006 Turning the extension off hands zoom back to GNOME
  GNOME turns extensions off while the screen is locked and on again after. Turning Scroll
  Zoom off leaves zoom on at its level, drawn by GNOME's own scaling, and turning it on
  again brings its smoothing back.

  Scenario: Off and on again, zoom stays and smoothing returns
    Given zoom is on at 4x over the test pattern
    When the extension is turned off
    Then zoom is on at 4x
    And the zoomed screen is the one GNOME's standard scaling draws
    When the extension is turned on
    Then the zoomed text is sharp again
