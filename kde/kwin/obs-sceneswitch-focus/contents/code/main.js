// Tell obs-sceneswitch which app just got focus. OBS runs under XWayland and
// can't see native Wayland windows, KWin can. obs-sceneswitch decides what, if
// anything, to switch to; this only reports.
//
// Only app windows and their dialogs count: panels, popups, the desktop and
// KRunner come and go without being a change of what you're working in.
// If obs-sceneswitch isn't running the call fails and nothing happens.

function report(w) {
    if (!w || !(w.normalWindow || w.dialog)) {
        return;
    }
    callDBus("io.github.iammrcupp.SceneSwitch", "/SceneSwitch", "io.github.iammrcupp.SceneSwitch",
             "Focus", String(w.resourceClass || ""), String(w.desktopFileName || ""));
}

workspace.windowActivated.connect(report);
