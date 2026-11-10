@invariant @shell
Feature: SZ-007 GNOME's keyboard zoom glides too
  GNOME's zoom shortcuts, Super+Alt+= and Super+Alt+-, and the zoom slider in Settings set
  GNOME's zoom level directly. The zoom glides to that level, as it does for the wheel.

  Scenario: Setting GNOME's zoom level glides to it
    Given zoom is on at 2x
    When GNOME's zoom level is set to 3x, as its keyboard shortcut does
    Then zoom is on at 3x
    And no frame on the way covered more than a fifth of the change
    And it took at least 10 frames to get there
