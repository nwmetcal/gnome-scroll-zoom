@invariant @shell
Feature: SZ-005 Smoothing turns off and on
  With smoothing off, each zoomed pixel is a hard square, for looking at pixels as they are.
  Super+Alt+\ turns smoothing off and on, as Option+Cmd+\ does on macOS.

  Scenario: With smoothing off, zoomed pixels are hard squares
    Given zoom is on at 4x over the test pattern
    When smoothing is turned off in the settings
    Then every whole zoomed pixel of the pattern is one flat square of 4 by 4

  Scenario: Super+Alt+backslash turns smoothing off and on again
    Given zoom is on at 4x over the test pattern
    When Super, Alt, and backslash are pressed together
    Then every whole zoomed pixel of the pattern is one flat square of 4 by 4
    When Super, Alt, and backslash are pressed together
    Then the zoomed text is sharp again
