@golden @shell
Feature: SZ-004 Zoomed text and lines are drawn sharp
  GNOME stretches the zoomed screen with bilinear filtering, which blurs text. With
  smoothing on, Scroll Zoom redraws text and lines with sharp edges instead, leaves smooth
  gradients as smooth scaling draws them, and puts everything exactly where GNOME's own zoom
  would. Sharp edges keep the font's own shapes: square corners stay square, strokes keep
  the weight the font gives them, and a serif font's thin strokes stay as thin as it draws
  them beside its thick ones, so zoomed text reads as the font it is. Each pixel of the
  screen keeps the ink it had: the zoomed view shrunk back to the screen's own size is the
  screen again. The test pattern has a line of text, two thin stems, a square set off the
  pixel grid, a gradient, and a line of serif capitals, its text antialiased in gray, as GTK
  draws text.

  At 6x each pixel of the screen is drawn 6 pixels wide, enough to see a corner rounded or a
  stroke thickened. A crisp right angle measures about 0.3 pixels in from where its edges
  meet, and GNOME's blurry scaling about 1.7; a corner within 1 pixel reads as square.
  GNOME's scaling keeps the ink of what it scales, so text within 5 percent of its ink is
  drawn at the font's weight: 5 percent of a stroke 6 pixels wide is under a third of a
  pixel. Shrunk back to the screen's size, GNOME's blur leaves each pixel's ink 10 percent
  off on average, as it moves ink between neighbours. Within 5 percent, and drawn in ink and
  paper with at most a third of the in-between pixels GNOME's scaling leaves, each edge sits
  where the font put it, so a thin stroke cannot come out wide and pale.

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

  Scenario: Square ends and corners stay square
    Given zoom is on at 6x over the test pattern
    When the zoomed screen is captured with sharp smoothing
    Then every corner of the two stems and the square is within 1 pixel of a right angle

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
    When the zoomed screen is captured with sharp smoothing and with GNOME's standard scaling
    Then shrunk back to its unzoomed size, the serif line keeps each pixel's ink within 5 percent on average
    And the serif line has at most a third as many in-between pixels as with GNOME's scaling
