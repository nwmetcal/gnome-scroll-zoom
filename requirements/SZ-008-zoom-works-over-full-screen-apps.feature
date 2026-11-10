@invariant @shell
Feature: SZ-008 Zoom works over full-screen apps
  Full-screen games, video, virtual machines, and remote desktops take over the screen, and
  GNOME routes their input differently: an X11 app, as most games are, runs through
  Xwayland, and some apps take over the keyboard's shortcuts. A person with low vision needs
  to zoom into all of them the same way. The test app fills the screen with text and a bar
  that moves every frame, as a game or a video keeps drawing.

  Four notches turned quickly zoom past 1.2 to the fourth, 2.07x, since a fast spin zooms
  further (SZ-002), and eight notches down undo four up whatever the speed of each spin.
  Sharp text has at most two thirds of the in-between pixels GNOME's own scaling leaves, the
  mark SZ-004 sets for text. It also matches the same text drawn by GNOME's scaling, by a
  correlation of at least 0.8, so a zoomed view that has lost the app, blank or dark, fails:
  sharp text drawn over the app scores about 0.92 against GNOME's, and a blank view 0.
  The bar moves 0.1 pixels a millisecond and goes round once every 2.8 s, so two captures
  300 ms or more apart, and under 2.5 s, find a live view's bar at least 40 pixels of the
  zoomed screen from where it was, and a view that has stopped showing what the app draws
  finds it 0 pixels away.

  Scenario Outline: Super and scrolling zoom in and out over a full-screen <kind> app
    Given a full-screen <kind> app
    When Super is held and the wheel turns 4 notches up
    Then zoom is on above 2x
    And the app's zoomed text matches GNOME's own, by a correlation of at least 0.8
    And the app's zoomed text has at most two thirds of GNOME's in-between pixels
    When Super is held and the wheel turns 8 notches down
    Then zoom is off

    Examples:
      | kind    |
      | Wayland |
      | X11     |

  Scenario: Super and scrolling zoom over an app allowed to take over the keyboard's shortcuts
    Given a full-screen Wayland app the person allowed to take over the keyboard's shortcuts
    When Super is held and the wheel turns 4 notches up
    Then zoom is on above 2x

  Scenario: The zoomed view of an app that keeps drawing stays live
    Given a full-screen Wayland app
    And zoom is on at 3x over the app's moving bar
    When the zoomed screen is captured twice, 300 ms apart
    Then the moving bar is at least 40 pixels from where it was
