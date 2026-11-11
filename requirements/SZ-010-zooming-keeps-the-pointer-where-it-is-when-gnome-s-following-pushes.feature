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
  grows with the zoom. So a pointer kept where it is stays where it was drawn when it was last
  put there, by moving, as zoom came on, as Scroll Zoom's following of keyboard focus or the
  text cursor moved the view under it, or as a zoom under another of GNOME's ways of following
  did, or as near to it as keeps its whole image on the screen and the view within the screen:
  no further right than the screen's width less 24 pixels times the zoom, no further down than
  its height less the same, and, as zoom goes back toward 1x and the view grows to fill the
  screen, back toward where the pointer itself is. Past 6.25x the pointer at 1100, 650 has less
  room than that below it, and past 7.5x to its right. Kept so, the view stays still as the
  pointer then moves within it, and where the pointer is drawn depends only on where it was put
  and the zoom, however the zoom got there. A later zoom without a move, and a spin that zooms
  in deep and turns back, bring the pointer back as the room comes back, even past the maximum
  zoom, where the zoom stops while the spin goes on, and after a rest there, of the wheel or of
  fingers on the touchpad. A zoom that GNOME's level started, by its keyboard zoom or its
  slider, goes GNOME's way, and a wheel notch during it keeps the pointer where it is drawn as
  the notch comes, within 4 pixels, since GNOME's glide can still move it in the frame before
  the notch takes hold. The pointer itself does not move. Most of these scenarios zoom with the
  pointer at 1100, 650, far from the screen's middle, where GNOME's push left the pointer drawn
  108 pixels right of and 78 pixels below where it was once zoom reached 3x. "Within 2 pixels"
  allows for the rounding of where the view sits, and a view staying where it was on the screen
  is measured times the zoom, as the screen shows it.

  Under GNOME's following that moves with the contents, the view sits where GNOME Shell 50's
  own magnifier puts it for the pointer's place on the screen. Under no following, the view's
  middle stays where GNOME had it before zoom came on, as far as the view at each zoom can
  stay within the screen, since GNOME keeps where it put the view's middle at the zoom before.
  Each scenario starts with GNOME's view at the screen's middle and its own following at rest;
  the toggle's under no following starts instead from zoom last on, at 2x around 400, 250.

  With GNOME's Extend Outside Screen Edges on, the view may stay as far past the screen's edges
  as it was when the pointer was last put there, however far that is: GNOME's push takes it past
  the right and bottom edges to show the pointer's whole image, and Scroll Zoom's following past
  any edge to show what it follows with room around it, even a control on a window partly off
  the screen. Following leaves 24 pixels of room around what it shows, so for a control wholly
  on the screen it takes the view no more than 24 pixels past an edge, and a scenario that wants
  it further puts the control past the edge. GNOME does not move its view where the view's
  middle would leave the screen, so following a control further off than that leaves the view
  where it is, and the pointer's kept place with it. It may also go past the right and bottom
  edges as far as the pointer's whole image needs now, and no further. So as zoom goes back
  toward 1x the view still grows back to fill the screen but for that, and zoom going off moves
  the pointer by up to that much more than zoom going off from 1.01x moves it anyway, as GNOME's
  own toggle does with its view past the edge. How far the view is past an edge is in the
  screen's own pixels, as at 1x.

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

  Scenario: A spin that rests at the maximum zoom and turns back brings the pointer back
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 26 notches up, rests 1000 ms, and turns 6 down
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Fingers resting on the touchpad at the maximum zoom, then swiping back, bring it back
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and two fingers swipe 400 pixels up, then 120 back after resting 1000 ms
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: With GNOME's view let past the screen's edges, zooming out brings it back to the screen
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And zoom is off
    And the pointer is at 100, 400
    When Super is held and the wheel turns 8 notches up
    And the pointer moves 100 pixels left
    And the pointer moves 100 pixels right
    And Super is held and the wheel turns 12 notches down
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    And zoom is off

  Scenario: After following focus moves the view, zooming keeps the pointer where it is drawn
    Given GNOME's own following pushes the view at its edges
    And Scroll Zoom follows keyboard focus
    And the focus test app is open
    And zoom is off
    And the pointer is at 300, 300
    When Super is held and the wheel turns 4 notches up
    And Tab moves keyboard focus to the middle button, and the view moves to show it
    And Super is held and the wheel turns 1 notch up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Zoom coming on again by the wheel, with no move since it went off, keeps the pointer
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    And the pointer moves 100 pixels left
    And Super is held and the wheel turns 12 notches down
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    And zoom is off
    When Super is held and the wheel turns 6 notches up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: GNOME's toggle turning zoom on again, with no move since it went off, keeps it
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    And the pointer moves 100 pixels left
    And Super is held and the wheel turns 12 notches down
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    And zoom is off
    When GNOME's zoom toggle turns zoom on
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: With GNOME's view let past the edges, zooming out after a push at the right comes back
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And zoom is off
    And the pointer is at 1180, 400
    When Super is held and the wheel turns 8 notches up
    And the pointer moves 100 pixels right
    And the pointer moves 100 pixels left
    And Super is held and the wheel turns 12 notches down
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    And zoom is off

  Scenario: With GNOME's view let past the screen's edges, zooming keeps it where the push left it
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And zoom is off
    And the pointer is at 1100, 400
    When GNOME's zoom toggle turns zoom on
    And the pointer moves 170 pixels right
    And the pointer moves 50 pixels left
    And Super is held and the wheel turns 3 notches up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: After following focus takes the view past the screen's edges, zooming keeps it there
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And Scroll Zoom follows keyboard focus
    And the focus test app is open with its first button in the screen's top-left corner
    And zoom is off
    And the pointer is at 300, 300
    When Super is held and the wheel turns 4 notches up
    And Tab moves keyboard focus to the middle button, and the view moves to show it
    And Shift+Tab moves keyboard focus back to the first button, and the view moves to show it
    Then the view is past the screen's left and top edges
    When Super is held and the wheel turns 1 notch up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Zooming out after following takes the view past the screen's edges brings it back
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And Scroll Zoom follows keyboard focus
    And the focus test app is open with its first button in the screen's top-left corner
    And zoom is off
    And the pointer is at 300, 300
    When Super is held and the wheel turns 4 notches up
    And Tab moves keyboard focus to the middle button, and the view moves to show it
    And Shift+Tab moves keyboard focus back to the first button, and the view moves to show it
    Then the view is past the screen's left and top edges
    When Super is held and the wheel turns 8 notches down
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    And zoom is off

  Scenario: A spin in and back out after following takes the view past the edges keeps it there
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And Scroll Zoom follows keyboard focus
    And the focus test app is open with its first button in the screen's top-left corner
    And zoom is off
    And the pointer is at 300, 300
    When Super is held and the wheel turns 4 notches up
    And Tab moves keyboard focus to the middle button, and the view moves to show it
    And Shift+Tab moves keyboard focus back to the first button, and the view moves to show it
    Then the view is past the screen's left and top edges
    When Super is held and the wheel turns 3 notches up and then 3 down in one spin
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: After following a control past the screen's right edge, zooming keeps the view there
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And Scroll Zoom follows keyboard focus
    And the focus test app is open in a window at 920, 200, past the screen's right edge
    And zoom is off
    And the pointer is at 800, 400
    When Super is held and the wheel turns 4 notches up
    And Shift+Tab moves keyboard focus back to the first button, and the view moves to show it
    And Tab moves keyboard focus to the middle button, and the view moves to show it
    Then the view is past the screen's right edge by more than 24 pixels
    When Super is held and the wheel turns 1 notch up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Following that GNOME's view cannot go to leaves where the pointer is kept as it was
    Given GNOME's own following pushes the view at its edges
    And Scroll Zoom follows keyboard focus
    And the focus test app is open in a window moved 300 pixels past the screen's left edge
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 26 notches up
    And Shift+Tab moves keyboard focus back to the first button, where GNOME's view cannot go
    And Super is held and the wheel turns 8 notches down
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: After following a control on a window partly off the screen, zooming keeps the view
    Given GNOME's own following pushes the view at its edges
    And GNOME's zoomed view may go past the screen's edges
    And Scroll Zoom follows keyboard focus
    And the focus test app is open in a window moved 100 pixels past the screen's left edge
    And zoom is off
    And the pointer is at 400, 300
    When Super is held and the wheel turns 4 notches up
    And Shift+Tab moves keyboard focus back to the first button, and the view moves to show it
    Then the view is past the screen's left edge by more than 24 pixels
    When Super is held and the wheel turns 1 notch up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Following the text cursor within the view leaves where the pointer is kept as it was
    Given GNOME's own following pushes the view at its edges
    And Scroll Zoom follows the text cursor
    And the focus test app is open, moving its text cursor on its own
    And zoom is off
    And the pointer is at 755, 572
    When Super is held and the wheel turns 16 notches up, rests 1500 ms, and turns 6 down
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: After a zoom under another of GNOME's ways of following, push keeps the pointer there
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 4 notches up
    And GNOME's Follow Behavior is set to Remains Centered
    And Super is held and the wheel turns 1 notch up
    And GNOME's Follow Behavior is set to Pushes Contents Around
    And Super is held and the wheel turns 1 notch up
    Then every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: A wheel notch during a zoom GNOME's level started keeps the pointer where it is
    Given GNOME's own following pushes the view at its edges
    And zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 8 notches up
    And GNOME's zoom level is set to 2x, and 300 ms later the wheel turns 1 notch up with Super
    Then every frame from the notch kept the pointer where it was drawn then, within 4 pixels
