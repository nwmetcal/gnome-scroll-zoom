@golden @shell
Feature: SZ-004 Zoomed text and lines are drawn sharp
  GNOME stretches the zoomed screen with bilinear filtering, which blurs text. With
  smoothing on, Scroll Zoom redraws text and lines with sharp edges instead, leaves smooth
  gradients as smooth scaling draws them, and puts everything exactly where GNOME's own zoom
  would. Sharp edges keep the font's own shapes: square corners stay square, strokes keep
  the weight the font gives them, and a serif font's thin strokes stay as thin as it draws
  them beside its thick ones, so zoomed text reads as the font it is. Each pixel of the
  screen keeps the ink it had: the zoomed view shrunk back to the screen's own size is the
  screen again. The test pattern has a line of text, two thin stems, a gradient, and a line
  of serif capitals.

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

  Scenario: The stems' square ends stay square
    Given zoom is on at 6x over the test pattern
    When the zoomed screen is captured with sharp smoothing
    Then every corner of the two stems is within 1 pixel of a right angle

  Scenario Outline: Zoomed text keeps the weight of its strokes
    Given zoom is on at 6x over the test pattern's <part>
    When the zoomed screen is captured with sharp smoothing and with GNOME's standard scaling
    Then the <part> carries within 5 percent of the ink it carries with GNOME's scaling

    Examples:
      | part       |
      | text       |
      | serif line |

  Scenario: A serif font keeps its thick and thin strokes
    Given the test pattern is captured unzoomed
    And zoom is on at 6x over the test pattern's serif line
    When the zoomed screen is captured with sharp smoothing
    Then shrunk back to its unzoomed size, the serif line keeps each pixel's ink within 5 percent on average
