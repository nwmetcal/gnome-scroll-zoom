@invariant @shell
Feature: SZ-010 Zooming keeps the pointer where it is when GNOME's following pushes
  GNOME's own setting, Settings > Accessibility > Zoom > Follow Behavior, decides how the
  zoomed view follows the pointer, and Scroll Zoom follows it. With "Pushes Contents Around"
  the view stays still while the pointer moves within it, and moves only as the pointer
  pushes past its edge, as the Mac's "Only when the pointer reaches an edge" does. Zooming
  then keeps the pointer where it is on the screen, with what is under it still under it, so
  neither jumps toward an edge: on every frame of a glide, in or out, by the wheel or a
  touchpad, and as zoom comes on, by the wheel or by GNOME's own toggle. Under GNOME's other
  ways of following, "Moves with Contents", its default, "Remains Centered", and none, the
  view goes where that way puts it, as SZ-001 says.

  The pointer is drawn where the zoomed view shows the point it is on: its place in the view
  times the zoom. With zoom off it is drawn where it is. GNOME's push keeps the whole of the
  pointer's image in the view, and that image, 24 pixels across and down in the test shell,
  grows with the zoom. So a pointer kept where it is stays where it was drawn before the zoom
  began, or as near to it as keeps its whole image on the screen and, unless GNOME lets its view
  go past the screen's edges, the view within the screen: no further right than the screen's
  width less 24 pixels times the zoom, no further down than its height less the same, and, as
  zoom goes back toward 1x and the view grows to fill the screen, back toward where the pointer
  itself is. Past 6.25x the pointer at 1100, 650 has less room than that below it, and past 7.5x
  to its right. Kept so, the view stays still as the pointer then moves within it, and a spin
  that zooms in deep and turns back brings the pointer back as the room comes back, even past
  the maximum zoom, where the zoom stops while the spin goes on. A zoom that GNOME's level
  started, by its keyboard zoom or its slider, goes GNOME's way, and a wheel notch during it
  keeps the pointer where it is drawn as the notch comes, within 4 pixels, since GNOME's glide
  still moves it a little in the frames before the notch takes hold. The pointer itself does not
  move. Most of these scenarios zoom with the pointer at 1100, 650, far from the screen's
  middle, where GNOME's push left the pointer drawn 108 pixels right of and 78 pixels below
  where it was once zoom reached 3x. "Within 2 pixels" allows for the rounding of where the view
  sits, and a view staying where it was on the screen is measured times the zoom, as the screen
  shows it.

  Under GNOME's following that moves with the contents, the view sits where GNOME Shell 50's
  own magnifier puts it for the pointer's place on the screen. Under no following, the view's
  middle stays where GNOME had it before zoom came on, as far as the view at each zoom can
  stay within the screen, since GNOME keeps where it put the view's middle at the zoom before.
  Each scenario starts with GNOME's view at the screen's middle and its own following at rest;
  the toggle's under no following starts instead from zoom last on, at 2x around 400, 250.

  With GNOME's Extend Outside Screen Edges on, GNOME lets the view reach past the screen's
  right and bottom edges, so near them the pointer's whole image is kept in the view there.

  GNOME can show its zoomed view on half the screen instead (Magnifier View > Screen Area).
  There the view is that half: the pointer is drawn from the half's own corner, at its place in
  the view times the zoom, and kept within the half as within the screen. The bottom half's
  corner is at 0, 400 and the right half's at 640, 0. A pointer at 1100, 390 is near the top
  half's lower edge, and one at 630, 400 near the left half's right edge, so its image, grown
  by the zoom, would run past the half if kept where it was.

  Scenario: The wheel turning zoom on keeps the pointer where it is
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    Then zoom is on
    And every frame kept the pointer where it was on the screen, within 2 pixels
    And GNOME's own following still pushes the view at its edges

  Scenario: Zooming further in and back out, after the pointer moves, keeps it where it is
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    And the pointer moves 100 pixels left
    Then the view stayed where it was on the screen as the pointer moved, within 2 pixels
    When Super is held and the wheel turns 3 notches up
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    When Super is held and the wheel turns 3 notches down
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    And zoom is on

  Scenario: Zooming in deep keeps the pointer's image on the screen and the view still after
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 16 notches up
    Then zoom is on at 20x
    And every frame kept the pointer where it was on the screen, within 2 pixels
    When the pointer moves 10 pixels left
    Then the view stayed where it was on the screen as the pointer moved, within 2 pixels

  Scenario: A touchpad swipe in and back out keeps the pointer where it is
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and two fingers swipe 30 pixels up
    Then zoom is on
    And every frame kept the pointer where it was on the screen, within 2 pixels
    When Super is held and two fingers swipe 30 pixels down
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: GNOME's zoom toggle turning zoom on keeps the pointer where it is
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When GNOME's zoom toggle turns zoom on
    Then zoom is on
    And every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Under GNOME's following that moves with the contents, zooming goes where it says
    Given GNOME's own following moves the view with its contents
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    Then every frame had the view where GNOME's moving with the contents puts it, within 2 pixels
    When Super is held and the wheel turns 3 notches down
    Then every frame had the view where GNOME's moving with the contents puts it, within 2 pixels

  Scenario: Under no following of GNOME's, zooming keeps the view's middle where it is
    Given GNOME's own following follows nothing
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    Then every frame kept the view's middle where GNOME had it, within 2 pixels

  Scenario: Under GNOME's following that moves with the contents, its toggle goes where it says
    Given GNOME's own following moves the view with its contents
    And zoom is off
    And the pointer is at 1100, 650
    When GNOME's zoom toggle turns zoom on
    Then every frame had the view where GNOME's moving with the contents puts it, within 2 pixels

  Scenario: Under no following of GNOME's, its toggle keeps the view's middle where it is
    Given zoom was last on at 2x around 400, 250 and is off
    And GNOME's own following follows nothing
    And the pointer is at 1100, 650
    When GNOME's zoom toggle turns zoom on
    Then every frame kept the view's middle where GNOME had it, within 2 pixels

  Scenario: A spin that zooms in deep and turns back brings the pointer back to where it was
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 16 notches up and then 6 down in one spin
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: In GNOME's zoomed view on the top half of the screen, the wheel keeps the pointer
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view is on the top half of the screen
    And zoom is off
    And the pointer is at 1100, 300
    When Super is held and the wheel turns 6 notches up
    Then zoom is on
    And every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: In GNOME's zoomed view on the left half of the screen, its toggle keeps the pointer
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view is on the left half of the screen
    And zoom is off
    And the pointer is at 300, 400
    When GNOME's zoom toggle turns zoom on
    Then zoom is on
    And every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: In GNOME's zoomed view on the bottom half of the screen, the wheel keeps the pointer
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view is on the bottom half of the screen
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    When Super is held and the wheel turns 3 notches up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: In GNOME's zoomed view on the right half of the screen, its toggle keeps the pointer
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view is on the right half of the screen
    And zoom is off
    And the pointer is at 1000, 400
    When GNOME's zoom toggle turns zoom on
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Near the top half's lower edge, the wheel keeps the pointer's image within the half
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view is on the top half of the screen
    And zoom is off
    And the pointer is at 1100, 390
    When Super is held and the wheel turns 6 notches up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Near the left half's right edge, the toggle keeps the pointer's image within the half
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view is on the left half of the screen
    And zoom is off
    And the pointer is at 630, 400
    When GNOME's zoom toggle turns zoom on
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: A swipe to the maximum zoom and back, without lifting, brings the pointer back
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and two fingers swipe 400 pixels up and 120 back without lifting
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: A spin past the maximum zoom and back brings the pointer back to where it was
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 26 notches up and then 6 down in one spin
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: With GNOME's view let past the screen's edges, zooming keeps the pointer in view
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And zoom is off
    And the pointer is at 1270, 790
    When Super is held and the wheel turns 6 notches up
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    When the pointer moves 10 pixels left
    Then the view stayed where it was on the screen as the pointer moved, within 2 pixels

  Scenario: A wheel notch during a zoom GNOME's level started keeps the pointer where it is
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 8 notches up
    And GNOME's zoom level is set to 2x, and 300 ms later the wheel turns 1 notch up with Super
    Then every frame from the notch kept the pointer where it was drawn then, within 4 pixels
