@invariant
Feature: SZ-002 Zoom glides from level to level
  Zoom never jumps. Each wheel notch moves the zoom one step, 1.2x by default, and the view
  glides there over about a fifth of a second, so a run of notches is one motion. A fast spin
  goes further per notch, as scroll acceleration does. A touchpad swipe that is still moving
  when the fingers lift keeps zooming and coasts to a stop. Frames are judged at 144 Hz, the
  rate of the monitor this is built on.

  Scenario: One notch glides to its level
    Given the zoom is at 1x
    When the wheel turns 1 notch up
    Then the zoom comes to rest at 1.2x
    And no frame changes the zoom by more than 2 percent
    And the zoom is 90 percent of the way there between 150 and 300 ms after the notch

  Scenario: Slow notches add one step each
    Given the zoom is at 1x
    When the wheel turns 5 notches up, 200 ms apart
    Then the zoom comes to rest at 2.488x

  Scenario: A fast spin goes further per notch
    Given the zoom is at 1x
    When the wheel turns 10 notches up, 25 ms apart
    Then the zoom comes to rest above 8x

  Scenario: Turning the wheel back stops the glide where it is
    Given the zoom is at 4x
    When the wheel turns 3 notches up and, 30 ms later, 1 notch down
    Then the zoom comes to rest one step below where it was when the wheel turned back

  Scenario: A swipe still moving when the fingers lift coasts to a stop
    Given the zoom is at 1x
    When two fingers swipe up at 2 levels a second for 200 ms and lift
    Then the zoom keeps going after the lift, to between 1.5 and 2.2 times where it was
    And the zoom comes to rest within 2 seconds of the lift

  Scenario: A swipe that has stopped when the fingers lift does not coast
    Given the zoom is at 1x
    When two fingers swipe up at 0.1 levels a second for 100 ms and lift
    Then the zoom comes to rest where it was at the lift

  Scenario Outline: Zoom stays between 1x and the maximum
    Given the zoom is at <start>x
    When the wheel turns <notches> notches <direction>
    Then the zoom comes to rest at <end>x

    Examples:
      | start | notches | direction | end |
      | 19    | 5       | up        | 20  |
      | 1.3   | 5       | down      | 1   |

  Scenario: A late frame does not lurch
    Given the zoom is at 1x
    When the wheel turns 1 notch up and the next frame comes 500 ms late
    Then that frame moves the zoom less than half a step
