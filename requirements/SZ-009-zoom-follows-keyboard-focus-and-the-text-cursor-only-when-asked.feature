@invariant @shell
Feature: SZ-009 Zoom follows keyboard focus and the text cursor only when asked
  GNOME's own zoom moves the view to wherever keyboard focus goes and wherever a text cursor
  moves, even a text cursor an app moves on its own, as a terminal does as it prints. When
  the pointer has moved in the last second it waits, then jumps, so the view leaves what the
  person was reading, again and again. Scroll Zoom keeps the view where the pointer puts it:
  following keyboard focus and following the text cursor are two settings of its own, both
  off until the person turns them on, whatever GNOME's own settings for them say, and a
  change to GNOME's own settings while Scroll Zoom is on does not bring them back. Turned on,
  each brings the whole of the focused control or the text cursor into view, from any side and
  each time it moves, moving the view only as far as that takes, so what was in view stays
  close by, and leaves the other kind of move alone. A follow GNOME was holding back when
  following is turned off, or when Scroll Zoom comes on, never lands, and Scroll Zoom coming
  on, at login or as the screen unlocks, undoes the following GNOME's settings asked for before
  it. Scroll Zoom leaves GNOME's own settings for following as they are, and turning Scroll
  Zoom off hands GNOME's own following back.

  The test app fills the screen. Its first button is at the top left, under the view the
  pointer puts at 200, 130 at 3x. Its middle button, covering 700 to 820 across and 380 to 420
  down, whose middle is at 760, 400, and its line of text, two characters whose cells cover
  740 to 756 across and 560 to 576 down in the test shell's monospace font, are out of that
  view and clear of the screen's edges, below and to the right of it. The view the pointer
  puts at 1000, 600 has the middle button above and to the left of it. GNOME follows focus and
  the text cursor unless told otherwise; these scenarios set its own settings to centre the
  view on them, the easiest place to measure. The test shell's pointer following is GNOME's
  "centered", so the view the pointer at 200, 130 puts is the screen's top-left corner, and
  at 1000, 600 the view's middle is the pointer, each within 2 pixels for the rounding of where
  the view sits. The view is watched for 3 s, three times as long as GNOME waits.

  GNOME holds a follow back while the pointer has moved in the last second, and a switch that
  is on waits the same way. A pointer moving 2 pixels back and forth every 50 ms, as a resting
  hand does, keeps a follow held, so these scenarios turn following off, or Scroll Zoom on or
  off, during such a move, or move focus on again, close the window, give another app focus,
  or move the view with the pointer, before the follow lands. What lands is worked out from
  the view and the focus as they are when the pointer rests: nothing, when what moved is no
  longer in the window that has focus.

  The text area of the test app's other layout covers 100 to 1200 across and 150 to 750 down,
  more than the view at 3x; with the pointer at 900, 600 the view lies inside it. Focus moving
  into a control the view already lies inside leaves the view where it is.

  At 5x the view the pointer puts at 1000, 700 is 256 by 160 pixels and has the line's text
  above and to the left of it. At 10x the view is 128 by 80 pixels, and the middle button fits
  in it; at 25x it is 51.2 by 32 pixels, and the line's text fits in it. Room around what is
  brought into view shrinks to what the view has, so all of it shows, and a text cursor moving
  within the view moves the view no more.

  A view's overshoot is how much further it moved, across and down, than showing the focus or
  the text cursor takes. A view brought to either and no further shows it, overshooting by at
  most 60 pixels: room for a margin around what it shows, such as the 24 pixels GNOME leaves
  for the pointer when it pushes the view. A view centred on either overshoots by more than
  110 pixels each way.
  GNOME centres the view on the top-left corner of the text cursor's cell, up to 8 pixels
  from the middle of the line's text, so a view centred on the text cursor is within 10
  pixels of that middle.

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
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: GNOME's own settings changing while Scroll Zoom is on leave focus unfollowed
    Given the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When GNOME's own settings change to push the view to keyboard focus and to the text cursor
    And Tab moves keyboard focus to the middle button
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels
    And GNOME's own settings still push the view to keyboard focus and to the text cursor

  Scenario: GNOME's own settings changing while Scroll Zoom is on leave the text cursor unfollowed
    Given the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    When GNOME's own settings change to push the view to keyboard focus and to the text cursor
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels
    And GNOME's own settings still push the view to keyboard focus and to the text cursor

  Scenario: Following keyboard focus, turned on, brings it into view and no further
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button whole, overshooting by at most 60 pixels
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: Following keyboard focus, turned on, brings it into view above and to the left too
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 1000, 600
    When Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button whole, overshooting by at most 60 pixels
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: Following keyboard focus, turned on, follows focus back to a control it followed before
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    And zoom goes off, Shift+Tab moves focus back to the first button, and zoom comes on again
    And Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button whole, overshooting by at most 60 pixels

  Scenario: Following keyboard focus, turned on at 10x, shows all of a control that fits
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 10x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button whole, overshooting by at most 60 pixels

  Scenario: Following keyboard focus, turned on, drops a held follow once focus goes back
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab and then Shift+Tab move focus out and back as the pointer moves for 1500 ms
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Following keyboard focus, turned on, follows from the view where the pointer rests
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves focus during a 1500 ms pointer move, and the pointer then goes to 760, 400
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Following the text cursor, turned on, brings it into view and no further
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And following the text cursor is turned on in Scroll Zoom's settings
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    Then after 3 s the view shows the line's text whole, overshooting by at most 60 pixels
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: Following keyboard focus, turned on, goes no further after GNOME's own settings change
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When GNOME's own settings change to centre the view on keyboard focus and on the text cursor
    And Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button whole, overshooting by at most 60 pixels
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: Following the text cursor, turned on, goes no further after GNOME's own settings change
    Given following the text cursor is turned on in Scroll Zoom's settings
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    When GNOME's own settings change to follow keyboard focus and the text cursor in proportion
    Then after 3 s the view shows the line's text whole, overshooting by at most 60 pixels
    And GNOME's own settings still follow keyboard focus and the text cursor in proportion

  Scenario: Following keyboard focus, turned on, follows it though GNOME's settings follow nothing
    Given GNOME's own settings follow neither keyboard focus nor the text cursor
    And following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button whole, overshooting by at most 60 pixels
    And GNOME's own settings still follow neither keyboard focus nor the text cursor

  Scenario: Following keyboard focus, turned on, still follows once GNOME's settings follow nothing
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When GNOME's own settings change to follow neither keyboard focus nor the text cursor
    And Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button whole, overshooting by at most 60 pixels

  Scenario: Following the text cursor, turned on, follows it though GNOME's settings follow nothing
    Given GNOME's own settings follow neither keyboard focus nor the text cursor
    And following the text cursor is turned on in Scroll Zoom's settings
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    Then after 3 s the view shows the line's text whole, overshooting by at most 60 pixels
    And GNOME's own settings still follow neither keyboard focus nor the text cursor

  Scenario: Following the text cursor, turned on, brings it into view above and to the left too
    Given following the text cursor is turned on in Scroll Zoom's settings
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 5x with the pointer at 1000, 700
    Then after 3 s the view shows the line's text whole, overshooting by at most 60 pixels

  Scenario: Following keyboard focus, turned on and off again, leaves focus unfollowed
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And following keyboard focus is turned on in Scroll Zoom's settings
    And following keyboard focus is turned off in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Following keyboard focus, turned on, leaves an app's own text cursor unfollowed
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Following the text cursor, turned on, leaves keyboard focus unfollowed
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And following the text cursor is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Turning the extension off hands GNOME's own following of focus back
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When the extension is turned off
    And Tab moves keyboard focus to the middle button
    Then after 3 s the view is centred on the middle button's middle, within 2 pixels
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: Turning the extension off hands GNOME's own following of the text cursor back
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    When the extension is turned off
    Then after 3 s the view is centred on the line's text, within 10 pixels
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: Following the text cursor, turned off while a follow is held, leaves the view alone
    Given the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    When following the text cursor is on while the pointer moves for 1500 ms, then off
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Turning the extension on while GNOME holds a follow leaves the view with the pointer
    Given GNOME's own settings centre the view on keyboard focus and on the text cursor
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    When the extension is turned off as the pointer moves for 1500 ms, and on as it stops
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels
    And GNOME's own settings still centre the view on keyboard focus and on the text cursor

  Scenario: Scroll Zoom coming on undoes GNOME's own following of focus
    Given the extension is turned off
    And GNOME's own settings centre the view on keyboard focus and on the text cursor
    And the extension is turned on
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Scroll Zoom coming on undoes GNOME's own following of the text cursor
    Given the extension is turned off
    And GNOME's own settings centre the view on keyboard focus and on the text cursor
    And the extension is turned on
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Following the text cursor, turned on at 25x, shows it whole and then holds still
    Given the maximum zoom is set to 32x in Scroll Zoom's settings
    And following the text cursor is turned on in Scroll Zoom's settings
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 25x with the pointer at 200, 130
    Then after 3 s the view shows the line's text whole, overshooting by at most 60 pixels
    And for the next 2 s the view stays where it is, within 2 pixels

  Scenario: Turning the extension off while a follow is held leaves GNOME's settings to decide
    Given GNOME's own settings follow neither keyboard focus nor the text cursor
    And following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves focus, and the extension is turned off, during a 1500 ms pointer move
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels
    And GNOME's own settings still follow neither keyboard focus nor the text cursor

  Scenario: Following keyboard focus, turned on, leaves a view already inside the focused control
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with a text area bigger than the view
    And zoom is on at 3x with the pointer at 900, 600
    When Tab moves keyboard focus into the text area
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Following keyboard focus, turned on, drops a held follow once its window closes
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves focus, and the app's window closes, during a 1500 ms pointer move
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Following the text cursor drops a held follow once another app takes focus
    Given the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    When following the text cursor comes on in a 6000 ms pointer move, and another app takes focus
    Then for 3 s every frame has the view where the pointer puts it, within 2 pixels

  Scenario: Scroll Zoom coming on with a switch on follows though GNOME's settings follow nothing
    Given following keyboard focus is turned on in Scroll Zoom's settings
    And the extension is turned off
    And GNOME's own settings follow neither keyboard focus nor the text cursor
    And the extension is turned on
    And the focus test app is open with its first button focused
    And zoom is on at 3x with the pointer at 200, 130
    When Tab moves keyboard focus to the middle button
    Then after 3 s the view shows the middle button whole, overshooting by at most 60 pixels

  Scenario: Following the text cursor, turned on, still follows once GNOME's settings follow nothing
    Given following the text cursor is turned on in Scroll Zoom's settings
    And GNOME's own settings follow neither keyboard focus nor the text cursor
    And the focus test app is open, moving the text cursor in its line on its own
    And zoom is on at 3x with the pointer at 200, 130
    Then after 3 s the view shows the line's text whole, overshooting by at most 60 pixels
