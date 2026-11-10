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
  meet, and GNOME's blurry scaling 1.7 at the stems and about 3 at the square; a corner
  within 1 pixel reads as square. GNOME's scaling keeps the ink of what it scales, so text
  within 5 percent of its ink is drawn at the font's weight: 5 percent of a stroke 6 pixels
  wide is under a third of a pixel. Shrunk back to the screen's size, GNOME's blur leaves
  each pixel's ink 11 percent off on average, as it moves ink between neighbours, and drawn
  as hard pixels the serif line keeps 72 percent of the in-between pixels GNOME's scaling
  leaves, where a crisp drawing keeps about 12, so a third tells them apart. A serif font's
  thin bars, the rows it draws partly inked with nothing above or below, are as tall zoomed
  as their ink: a row 0.6 inked is 3.6 pixels of full ink at 6x. The faint ends of the
  serifs and bars, under half inked, are held apart from the rest, so a drawing that keeps
  the rest crisp cannot spend their room on drawing the ends pale. A crisp drawing comes
  within about 0.4 pixels of their ink on average in both; bars drawn heavy, as hard pixels,
  or with GNOME's blur come 1.3 to 2.1 pixels off in one or both, and bicubic's faint ends
  1.5. Each pixel's ink kept, few in-between pixels, and thin bars as tall as their ink put
  each edge where the font put it, so a thin stroke cannot come out wide and pale.

  A letter GNOME's blurry scaling draws in one piece of at least half ink is drawn in one
  piece too, so a stem cut through or an arch parted from its stem shows.

  The edge position the README offers for bolder or thinner text moves only the edges:
  paper more than a pixel from any ink stays paper at the README's 0.55 as at the default
  0.5. At 7x the zoomed view's pixel centres fall on screen pixels, which 4x and 6x step over.

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
    And its thin bars at least half inked are drawn as tall as the font draws them, within 1 pixel on average
    And its thin bars' faint ends, under half inked, are drawn as tall as the font draws them, within 1 pixel on average

  Scenario Outline: Letters stay whole
    Given zoom is on at 6x over the test pattern's <part>
    When the zoomed screen is captured with sharp smoothing and with GNOME's standard scaling
    Then every letter of the <part> GNOME's scaling draws in one piece is drawn in one piece

    Examples:
      | part       |
      | text       |
      | serif line |

  Scenario Outline: Paper away from the text stays paper, bolder or not
    Given the test pattern is captured unzoomed
    And the edge position is set to <position>
    And zoom is on at 7x over the test pattern's text
    When the zoomed screen is captured with sharp smoothing
    Then the paper over a pixel from the text's ink stays within 2/255 of paper

    Examples:
      | position |
      | 0.5      |
      | 0.55     |
