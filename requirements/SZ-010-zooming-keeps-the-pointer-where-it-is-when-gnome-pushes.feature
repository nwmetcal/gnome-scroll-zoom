@invariant @shell
Feature: SZ-010 Zooming keeps the pointer where it is when GNOME's following pushes
  GNOME's own setting, Settings > Accessibility > Zoom > Follow Behavior, decides how the
  zoomed view follows the pointer, and Scroll Zoom follows it. With "Pushes Contents Around"
  the view stays still while the pointer moves within it, and moves only as the pointer
  pushes past its edge, as the Mac's "Only when the pointer reaches an edge" does. Zooming
  then keeps the pointer where it is on the screen, with what is under it still under it, so
  neither jumps toward an edge: on every frame of a glide, in or out, by the wheel or a
  touchpad, and as zoom comes on, by the wheel or by GNOME's own toggle. Under GNOME's other
  ways of following, the view goes where that way puts it (SZ-001).

  The pointer is drawn where the zoomed view shows the point it is on: its place in the view
  times the zoom. With zoom off it is drawn where it is. These scenarios zoom with the pointer
  at 1100, 650, far from the screen's middle, where GNOME's push left the pointer drawn 108
  pixels right of and 78 pixels below where it was once zoom reached 3x. A pointer kept where
  it is stays within 2 pixels of where it was drawn before the zoom began, for the rounding of
  where the view sits.

  Background:
    Given GNOME's own following pushes the view at its edges

  Scenario: The wheel turning zoom on keeps the pointer where it is
    Given zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    Then zoom is on
    And every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: Zooming further in and back out, after the pointer moves, keeps it where it is
    Given zoom is off
    And the pointer is at 1100, 650
    When Super is held and the wheel turns 6 notches up
    And the pointer moves 100 pixels left
    Then the view stayed where it was as the pointer moved, within 2 pixels
    When Super is held and the wheel turns 3 notches up
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    When Super is held and the wheel turns 3 notches down
    Then every frame kept the pointer where it was on the screen, within 2 pixels
    And zoom is on

  Scenario: A touchpad swipe keeps the pointer where it is
    Given zoom is off
    And the pointer is at 1100, 650
    When Super is held and two fingers swipe 30 pixels up
    Then zoom is on
    And every frame kept the pointer where it was on the screen, within 2 pixels

  Scenario: GNOME's zoom toggle turning zoom on keeps the pointer where it is
    Given zoom is off
    And the pointer is at 1100, 650
    When GNOME's zoom toggle turns zoom on
    Then zoom is on
    And every frame kept the pointer where it was on the screen, within 2 pixels
