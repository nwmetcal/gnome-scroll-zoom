@invariant @shell
Feature: SZ-009 Zoom follows keyboard focus and the text cursor only when asked
  GNOME's own zoom moves the view to wherever keyboard focus goes and wherever a text cursor
  moves, even a text cursor an app moves on its own, as a terminal does as it prints. When
  the pointer has moved in the last second it waits, then jumps, so the view leaves what the
  person was reading, again and again. Scroll Zoom keeps the view where the pointer puts it:
  following keyboard focus and following the text cursor are two settings of its own, both
  off until the person turns them on, whatever GNOME's own settings for them say, and a
  change to GNOME's own settings while Scroll Zoom is on does not bring them back. Turned on,
  each brings the focus or the text cursor into view, moving the view only as far as that
  takes, so what was in view stays close by. Scroll Zoom leaves GNOME's own settings for
  following as they are, and turning Scroll Zoom off hands GNOME's own following back.

  The test app fills the screen. Its first button is at the top left, under the view the
  pointer puts at 200, 130 at 3x. Its middle button, whose middle is at 760, 400, and its line
  of text, whose middle is at 760, 572, are out of that view and clear of the screen's edges.
  GNOME follows focus and the text cursor unless told otherwise; these scenarios set its own
  settings to centre the view on them, the easiest place to measure. The test shell's
  pointer following is GNOME's "centered", so the view the pointer at 200, 130 puts is the
  screen's top-left corner, within 2 pixels for the rounding of where the view sits. The view
  is watched for 3 s, three times as long as GNOME waits. A view that brings the focus or the
  text cursor into view has it inside, within 60 pixels of the view's edge; a view centred on
  it has it 133 pixels or more from every edge.

  Scenario: Keyboard focus moving out of view leaves the view with the pointer
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: An app moving its own text cursor out of view leaves the view with the pointer
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: GNOME's own settings changing while Scroll Zoom is on leave the view with the pointer
    Given the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When GNOME's own settings change to centre the view on keyboard focus and on the text cursor
    And Tab moves keyboard focus to the middle button
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Following keyboard focus, turned on, brings it into view and no further
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button's middle, within 60 pixels of its edge

  Scenario: Following the text cursor, turned on, brings it into view and no further
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And following the text cursor is turned on in Scroll Zoom's settings
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    Then after 3 s the view shows the line's middle, within 60 pixels of its edge

  Scenario: Turning the extension off hands GNOME's own following back
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When the extension is turned off
    And Tab moves keyboard focus to the middle button
    Then after 3 s the view is centred on the middle button's middle, within 2 pixels
