@invariant @shell
Feature: SZ-001 Holding Super and scrolling zooms the screen
  Holding the zoom keys, Super alone unless the settings name others with it, and turning a
  mouse wheel or swiping a touchpad zooms the whole screen in and out. Scrolling with any
  other keys held is left to the app under the pointer. Zoom centres on the pointer, every
  time zoom comes on, whether or not the pointer moved since the last time. Zooming all the
  way out turns zoom off, and GNOME's own zoom toggle then brings back the last level zoom
  rested at. Letting go of Super after zooming does not open the Activities overview.

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
    And the pointer is at 400, 260
    When Super is held and the wheel turns 2 notches up
    And Super is held and the wheel turns 8 notches down
    And Super is held and the wheel turns 2 notches up
    Then zoom is on
    And the zoomed view is centred on the pointer

  Scenario: Zooming all the way out turns zoom off and keeps the last level
    Given zoom is on at 3x
    When Super is held and the wheel turns 8 notches down
    Then zoom is off
    And GNOME's zoom toggle turns zoom on at 3x
