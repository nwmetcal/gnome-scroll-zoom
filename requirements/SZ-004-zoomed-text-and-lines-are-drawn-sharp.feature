@golden @shell
Feature: SZ-004 Zoomed text and lines are drawn sharp
  GNOME stretches the zoomed screen with bilinear filtering, which blurs text. With
  smoothing on, Scroll Zoom redraws text and lines with sharp edges instead, leaves smooth
  gradients as smooth scaling draws them, and puts everything exactly where GNOME's own zoom
  would. The test pattern has a line of text, two thin stems, and a gradient.

  Scenario: Text has half the blur of GNOME's own zoom
    Given zoom is on at 4x over the test pattern
    When the zoomed screen is captured with sharp smoothing and with GNOME's standard scaling
    Then the text has at most two thirds as many in-between pixels as with GNOME's scaling

  Scenario: A smooth gradient stays smooth
    Given zoom is on at 4x over the test pattern
    When the zoomed screen is captured with sharp smoothing and with soft smoothing
    Then the gradient differs between them by less than 1/255 on average

  Scenario Outline: The sharp view lines up with GNOME's own
    Given zoom is on at <zoom>x over the test pattern
    When the zoomed screen is captured with sharp smoothing and with GNOME's standard scaling
    Then the two line up with no shift

    Examples:
      | zoom |
      | 4    |
      | 3.3  |
