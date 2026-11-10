@invariant @shell
Feature: SZ-001 Holding Super and scrolling zooms the screen
  Holding the zoom keys, Super alone unless the settings name others with it, and turning a
  mouse wheel or swiping a touchpad zooms the whole screen in and out. Scrolling with any
  other keys held is left to the app under the pointer. Zooming all the way out turns zoom
  off, and GNOME's own zoom toggle then brings back the last level zoom rested at. Letting go
  of Super after zooming does not open the Activities overview.

  Each time zoom comes on, by the wheel or by GNOME's own toggle, and all the while the wheel
  turns, the zoomed view follows the pointer as GNOME's pointer tracking places it, as far as
  the edges of the screen allow. That holds whether or not the pointer moved since zoom was
  last on, and however slowly the wheel turns. These scenarios use GNOME's "centered"
  tracking, where the view's middle is the pointer, within 2 pixels for the rounding of where
  the view sits; under GNOME's other tracking, such as its default, "proportional", the view
  sits where that tracking puts it, except under "push", where zooming keeps the pointer
  where it is on the screen instead (SZ-010). Each pointer here is clear of the edges at the
  zoom its scenario reaches; the slow spin's, near a corner, is one the view can centre on
  only once zoom passes 3.2x, which takes that spin more than a second.

  Scenario: Super and the wheel turn zoom on
    Given zoom is off
    When Super is held and the wheel turns 1 notch up
    Then zoom is on at 1.2x
    And the Activities overview is closed

  Scenario: The wheel alone leaves zoom off
    Given zoom is off
    When the wheel turns 3 notches up with no key held
    Then zoom is off

  Scenario: Another key held with Super leaves zoom off
    Given zoom is off
    When Super and Ctrl are held and the wheel turns 3 notches up
    Then zoom is off

  Scenario: The keys to hold can be Super and Ctrl
    Given zoom is off
    And the keys to hold are set to Super and Ctrl
    When Super and Ctrl are held and the wheel turns 1 notch up
    Then zoom is on at 1.2x

  Scenario: Turning the wheel down with zoom off does nothing
    Given zoom is off
    When Super is held and the wheel turns 2 notches down
    Then zoom is off

  Scenario: A touchpad swipe zooms
    Given zoom is off
    When Super is held and two fingers swipe 30 pixels up
    Then zoom is on above 1.5x

  Scenario: Zooming in again without moving the pointer zooms around it
    Given zoom is off
    And the pointer is at 500, 320
    When Super is held and the wheel turns 2 notches up
    And Super is held and the wheel turns 8 notches down
    And Super is held and the wheel turns 2 notches up
    Then zoom is on
    And the zoomed view is centred on the pointer, within 2 pixels
    And every frame from zoom on had the view where centred tracking puts it, within 2 pixels

  Scenario: A slow spin that turns zoom on zooms around the pointer
    Given zoom is off
    And the pointer is at 200, 130
    When Super is held and the wheel turns 8 notches up, 250 ms apart
    Then zoom is on
    And the zoomed view is centred on the pointer, within 2 pixels
    And every frame from zoom on had the view where centred tracking puts it, within 2 pixels

  Scenario: GNOME's zoom toggle comes on around the pointer
    Given zoom is off
    And the pointer is at 500, 320
    When Super is held and the wheel turns 2 notches up
    And Super is held and the wheel turns 8 notches down
    And GNOME's zoom toggle turns zoom on
    Then zoom is on
    And the zoomed view is centred on the pointer, within 2 pixels
    And every frame from zoom on had the view where centred tracking puts it, within 2 pixels

  Scenario: Zooming all the way out turns zoom off and keeps the last level
    Given zoom is on at 3x
    When Super is held and the wheel turns 8 notches down
    Then zoom is off
    And GNOME's zoom toggle turns zoom on at 3x
