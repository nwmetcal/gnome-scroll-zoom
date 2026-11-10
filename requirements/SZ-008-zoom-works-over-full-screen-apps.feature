@invariant @shell
Feature: SZ-008 Zoom works over full-screen apps
  Full-screen games, video, virtual machines, and remote desktops take over the screen, and
  GNOME routes their input differently: an X11 app, as most games are, runs through
  Xwayland, and some apps take over the keyboard's shortcuts. A person with low vision needs
  to zoom into all of them the same way. The test app fills the screen with text and a bar
  that moves every frame, as a game or a video keeps drawing. Four notches turned quickly
  zoom past 1.2 to the fourth, 2.07x, since a fast spin zooms further (SZ-002). Sharp text
  has at most two thirds of the in-between pixels GNOME's own scaling leaves, the mark
  SZ-004 sets for text; and it matches the same text drawn by GNOME's scaling, by a
  correlation of at least 0.8, so a zoomed view that has lost the app, blank or dark, fails.
  Eight notches down undo four up whatever speed each spin was. The bar moves 0.4 pixels a millisecond, about 360 pixels of the
  screen in 300 ms at 3x, so a view that has stopped showing what the app draws moves it 0
  pixels and a live one at least 40.

  Scenario Outline: Super and scrolling zoom in and out over a full-screen <kind> app
    Given a full-screen <kind> app
    When Super is held and the wheel turns 4 notches up
    Then zoom is on above 2x
    And the app's zoomed text matches what GNOME's scaling shows, by a correlation of at least 0.8
    And the app's zoomed text has at most two thirds as many in-between pixels as with GNOME's scaling
    When Super is held and the wheel turns 8 notches down
    Then zoom is off

    Examples:
      | kind    |
      | Wayland |
      | X11     |

  Scenario: Super and scrolling zoom over an app allowed to take over the keyboard's shortcuts
    Given a full-screen Wayland app that the person has allowed to take over the keyboard's shortcuts
    When Super is held and the wheel turns 4 notches up
    Then zoom is on above 2x

  Scenario: The zoomed view of an app that keeps drawing stays live
    Given a full-screen Wayland app
    And zoom is on at 3x over the app's moving bar
    When the zoomed screen is captured twice, 300 ms apart
    Then the moving bar is at least 40 pixels from where it was
