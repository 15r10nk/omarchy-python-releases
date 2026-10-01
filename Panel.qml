pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui
import "Translations.js" as I18n
import "Selection.js" as Selection

Ui.Panel {
  id: root
  moduleName: "frank.python-releases"
  manageIpc: false
  property Item anchorItem: null
  property var hostWidget: null
  readonly property var barApi: root.bar
  readonly property var popupColors: Color.popups

  function switchPanel(direction) {
    return root.bar && typeof root.barApi.switchPanelFrom === "function"
      ? root.barApi.switchPanelFrom(root.hostWidget || root, direction) : false
  }

  function moveSelection(delta) {
    if (!root.branches.length) return
    root.upcomingOnly = false
    var index = root.branches.findIndex(function(b) { return b.version === root.selectedVersion })
    index = Math.max(0, Math.min(root.branches.length - 1, index + delta))
    root.selectedVersion = root.branches[index].version
    versions.positionViewAtIndex(index, ListView.Contain)
    details.contentY = 0
  }

  property var report: ({branches: [], next: null, warnings: [], fetchedAt: "", error: ""})
  property string processError: ""
  property bool favoriteSaveError: false
  readonly property string favorite: String(setting("favorite", ""))
  readonly property var displayLocale: Qt.locale()
  readonly property string language: I18n.resolveLanguage(displayLocale.name)

  function t(key, args) { return I18n.text(root.language, key, args) }
  property string selectedVersion: ""
  property bool upcomingOnly: false
  readonly property var branches: report.branches || []
  readonly property var selectedBranch: branches.find(function(b) { return b.version === selectedVersion }) || branches[0] || null
  readonly property var nextRelease: Selection.nextRelease(report, favorite, mode)
  readonly property string mode: ["feature", "stable", "all"].indexOf(setting("countdown", "feature")) >= 0 ? setting("countdown", "feature") : "feature"
  readonly property string modeLabel: favorite ? "★ Python " + favorite + " · " + t(mode === "all" ? "all" : "stable") : t(mode)
  readonly property string countdown: nextRelease ? (nextRelease.days === 0 ? t("today") : nextRelease.days === 1 ? t("oneDay") : t("days", {n: nextRelease.days})) : t("noDate")
  readonly property string errorText: favoriteSaveError ? t("favoriteSaveError") : processError ? t(processError) : (report.warnings || []).length ? t("partialError") : report.error ? t(report.fetchedAt ? "cachedError" : "emptyError") : ""
  readonly property bool stale: report.stale === true
  readonly property var visibleEvents: {
    var events = []
    if (upcomingOnly) {
      branches.forEach(function(b) {
        b.events.forEach(function(e) {
          if (e.date >= report.today && !e.confirmed) events.push(e)
        })
      })
      events.sort(function(a, b) { return a.date.localeCompare(b.date) })
    } else if (selectedBranch) {
      events = selectedBranch.events.slice().reverse()
    }
    return events
  }

  function dateLabel(value, estimated) {
    if (!value) return t("unspecified")
    var bits = value.split("-")
    var label = value
    if (bits.length >= 2) {
      var day = new Date(Number(bits[0]), Number(bits[1]) - 1, bits.length === 3 ? Number(bits[2]) : 1, 12)
      label = root.displayLocale.toString(day, bits.length === 3 ? root.displayLocale.dateFormat(Locale.ShortFormat) : (root.language === "zh" || root.language === "ja" ? "yyyy年M月" : root.language === "ko" ? "yyyy년 M월" : "MMM yyyy"))
    }
    return estimated ? t("estimated", {date: label}) : label
  }
  function statusLabel(value) { return t("status_" + value) }
  function toggleFavorite(version) {
    var entry = Object.assign({}, root.settings)
    entry.favorite = root.favorite === version ? "" : version
    if (!root.bar || !root.barApi.shell || !root.barApi.shell.updateEntryInline(root.moduleName, entry)) {
      root.favoriteSaveError = true
      return
    }
    root.settings = entry
    if (root.hostWidget) root.hostWidget.settings = entry
    root.favoriteSaveError = false
  }
  function kindLabel(value) { return t("kind_" + value) }
  function refresh(force) {
    if (worker.running) return
    worker.command = ["python3", decodeURIComponent(Qt.resolvedUrl("releases.py").toString().replace(/^file:\/\//, "")), "--mode", root.mode].concat(force ? ["--refresh"] : [])
    worker.running = true
  }
  function acceptData(text) {
    try {
      var data = JSON.parse(text)
      if (!Array.isArray(data.branches)) throw new Error("Ungültige Daten")
      root.report = data
      root.processError = ""
      if (!selectedVersion && data.branches.length) {
        selectedVersion = root.favorite || (data.next ? data.next.version.split(".").slice(0, 2).join(".") : data.branches[0].version)
      }
    } catch (error) {
      root.processError = "readError"
    }
  }

  Component.onCompleted: cached.running = true
  onModeChanged: Qt.callLater(function() { root.refresh(false) })
  Timer { interval: 60000; running: true; repeat: true; onTriggered: root.refresh(false) }
  Process {
    id: cached
    command: ["python3", decodeURIComponent(Qt.resolvedUrl("releases.py").toString().replace(/^file:\/\//, "")), "--cached", "--mode", root.mode]
    stdout: StdioCollector { onStreamFinished: if (!root.report.fetchedAt) root.acceptData(text) }
    // Quickshell 0.3.1 omits QProcess::ExitStatus from its tooling metadata.
    // qmllint disable signal-handler-parameters
    onExited: root.refresh(false)
    // qmllint enable signal-handler-parameters
  }
  Process {
    id: worker
    stdout: StdioCollector { onStreamFinished: root.acceptData(text) }
    stderr: StdioCollector {}
    // Quickshell 0.3.1 omits QProcess::ExitStatus from its tooling metadata.
    // qmllint disable signal-handler-parameters
    onExited: function(code) { if (code !== 0) root.processError = "fetchError" }
    // qmllint enable signal-handler-parameters
  }

  readonly property string barLabel: " " + (root.nextRelease ? root.nextRelease.version + " · " + (root.nextRelease.days === 0 ? root.t("today") : (root.nextRelease.days === 1 ? root.t("shortOneDay") : root.t("shortDays", {n: root.nextRelease.days}))) : root.favorite ? root.favorite + " · —" : worker.running ? "…" : "—") + (root.errorText || root.stale ? " *" : "")
  readonly property string barTooltip: root.modeLabel + "\n" + (root.nextRelease ? "Python " + root.nextRelease.version + " · " + root.dateLabel(root.nextRelease.date, true) : root.countdown) + "\n" + root.t("tooltip") + (root.errorText ? "\n" + root.errorText : "")

  Ui.KeyboardPanel {
    id: popup
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    contentWidth: popup.fittedContentWidth(Style.space(820))
    contentHeight: popup.cappedContentHeight(Style.space(650))
    focusTarget: content

    Ui.PanelKeyCatcher {
      id: content
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onMoveRequested: function(dx, dy) { if (dy !== 0) root.moveSelection(dy) }
      onActivateRequested: if (root.selectedBranch) root.toggleFavorite(root.selectedBranch.version)
      onTextKey: function(key) { if (key.toLowerCase() === "r") root.refresh(true) }

      Column {
        id: heading
        width: parent.width
        spacing: Style.space(8)
        Row {
          width: parent.width
          spacing: Style.space(8)
          Label { width: parent.width - refreshButton.width - closeButton.width - Style.space(16); text: "  " + root.t("title"); font.pixelSize: Style.space(23); font.bold: true }
          Action { id: refreshButton; text: worker.running ? root.t("loading") : root.t("refresh"); enabled: !worker.running; onClicked: root.refresh(true) }
          Action { id: closeButton; text: "×"; onClicked: root.close() }
        }
        Label { width: parent.width; text: root.modeLabel; color: Qt.alpha(root.popupColors.text, 0.65) }
        Label {
          width: parent.width
          text: root.nextRelease ? "Python " + root.nextRelease.version + "  ·  " + root.countdown + "  ·  " + root.dateLabel(root.nextRelease.date, true) : worker.running ? root.t("loadingDates") : root.countdown
          font.pixelSize: Style.space(20)
          color: Color.accent
        }
        Label {
          width: parent.width
          visible: text !== ""
          text: root.errorText || (root.stale ? root.t("stale") : "")
          color: Color.urgent
          font.pixelSize: Style.space(12)
        }
        Row {
          spacing: Style.space(8)
          Action { text: root.t("versions"); selected: !root.upcomingOnly; onClicked: root.upcomingOnly = false }
          Action { text: root.t("upcoming"); selected: root.upcomingOnly; onClicked: root.upcomingOnly = true }
        }
      }

      Row {
        anchors.top: heading.bottom
        anchors.topMargin: Style.space(16)
        anchors.bottom: footer.top
        anchors.bottomMargin: Style.space(12)
        width: parent.width
        spacing: Style.space(16)

        ListView {
          id: versions
          width: Style.space(190)
          height: parent.height
          visible: !root.upcomingOnly
          model: root.branches
          clip: true
          spacing: Style.space(4)
          boundsBehavior: Flickable.StopAtBounds
          Controls.ScrollBar.vertical: Controls.ScrollBar {}
          delegate: Rectangle {
            id: versionRow
            required property var modelData
            width: versions.width - Style.space(10)
            height: Style.space(57)
            radius: Style.space(5)
            color: root.selectedVersion === versionRow.modelData.version ? Qt.alpha(Color.accent, 0.16) : versionMouse.containsMouse ? Qt.alpha(root.popupColors.text, 0.06) : "transparent"
            Column {
              anchors.left: parent.left; anchors.leftMargin: Style.space(8)
              width: parent.width - Style.space(49)
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(3)
              Label { text: "Python " + versionRow.modelData.version; font.bold: true }
              Label { width: parent.width; maximumLineCount: 2; elide: Text.ElideRight; text: root.statusLabel(versionRow.modelData.status); font.pixelSize: Style.space(10); color: versionRow.modelData.status === "end-of-life" ? Qt.alpha(root.popupColors.text, 0.65) : Color.accent }
            }
            MouseArea { id: versionMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { root.selectedVersion = versionRow.modelData.version; details.contentY = 0 } }
            Action {
              anchors.right: parent.right
              anchors.rightMargin: Style.space(5)
              anchors.verticalCenter: parent.verticalCenter
              implicitWidth: Style.space(30)
              text: root.favorite === versionRow.modelData.version ? "★" : "☆"
              selected: root.favorite === versionRow.modelData.version
              Accessible.name: root.t(root.favorite === versionRow.modelData.version ? "unstar" : "star", {version: versionRow.modelData.version})
              Controls.ToolTip.visible: starHover.hovered
              Controls.ToolTip.text: Accessible.name
              HoverHandler { id: starHover }
              onClicked: root.toggleFavorite(versionRow.modelData.version)
            }
          }
        }

        Flickable {
          id: details
          width: parent.width - (versions.visible ? versions.width + parent.spacing : 0)
          height: parent.height
          contentWidth: width
          contentHeight: detailColumn.implicitHeight
          clip: true
          boundsBehavior: Flickable.StopAtBounds
          Controls.ScrollBar.vertical: Controls.ScrollBar {}
          Column {
            id: detailColumn
            width: details.width - Style.space(14)
            spacing: Style.space(10)
            Column {
              width: parent.width
              visible: !root.upcomingOnly && !!root.selectedBranch
              spacing: Style.space(8)
              Label { text: root.selectedBranch ? "Python " + root.selectedBranch.version : ""; font.pixelSize: Style.space(23); font.bold: true }
              Label { width: parent.width; text: root.selectedBranch ? root.statusLabel(root.selectedBranch.status) + "  ·  " + root.t("firstRelease", {date: root.dateLabel(root.selectedBranch.first, root.selectedBranch.firstEstimated)}) : "" }
              Label { width: parent.width; text: root.selectedBranch ? root.t("eol", {date: root.dateLabel(root.selectedBranch.eol, root.selectedBranch.eolEstimated)}) : ""; color: root.selectedBranch && root.selectedBranch.status === "end-of-life" ? Color.urgent : Color.accent }
              Label { width: parent.width; text: root.selectedBranch && root.selectedBranch.manager ? root.t("manager", {name: root.selectedBranch.manager}) : ""; visible: text !== ""; font.pixelSize: Style.space(12); color: Qt.alpha(root.popupColors.text, 0.65) }
              Action { text: root.t("openSchedule"); onClicked: if (root.selectedBranch) Qt.openUrlExternally(root.selectedBranch.url || "https://devguide.python.org/versions/") }
              Label { width: parent.width; text: root.selectedBranch && root.selectedBranch.scheduleError ? root.t("scheduleError") : ""; visible: text !== ""; color: Color.urgent }
            }
            Label { text: root.upcomingOnly ? root.t("plannedReleases") : root.t("milestones"); font.bold: true }
            Label { width: parent.width; text: root.t("provisional"); color: Qt.alpha(root.popupColors.text, 0.65); font.pixelSize: Style.space(12) }
            Label { width: parent.width; visible: root.visibleEvents.length === 0; text: worker.running ? root.t("loadingData") : root.t("noEvents") }
            Repeater {
              model: root.visibleEvents
              delegate: Rectangle {
                id: eventRow
                required property var modelData
                width: detailColumn.width
                height: eventColumn.implicitHeight + Style.space(18)
                color: eventMouse.containsMouse ? Qt.alpha(Color.accent, 0.12) : Qt.alpha(root.popupColors.text, 0.04)
                radius: Style.space(5)
                Column {
                  id: eventColumn
                  x: Style.space(9); y: Style.space(9)
                  width: parent.width - Style.space(18)
                  spacing: Style.space(4)
                  Label { width: parent.width; text: "Python " + I18n.eventVersion(eventRow.modelData) + "  ·  " + root.dateLabel(eventRow.modelData.date, !eventRow.modelData.confirmed && eventRow.modelData.date >= root.report.today); font.bold: true }
                  Label { width: parent.width; text: root.kindLabel(eventRow.modelData.kind) + "  ·  " + (eventRow.modelData.confirmed ? root.t("released") : eventRow.modelData.date >= root.report.today ? root.t("planned") : root.t("pepDate")) + "  ↗"; color: eventRow.modelData.date >= root.report.today ? Color.accent : Qt.alpha(root.popupColors.text, 0.65); font.pixelSize: Style.space(12) }
                }
                MouseArea { id: eventMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally(eventRow.modelData.url) }
              }
            }
          }
        }
      }

      Column {
        id: footer
        anchors.bottom: parent.bottom
        width: parent.width
        spacing: Style.space(4)
        Label { width: parent.width; text: root.t("sources"); font.pixelSize: Style.space(11); color: Qt.alpha(root.popupColors.text, 0.65) }
        Label { width: parent.width; text: (root.report.fetchedAt ? root.t("fetched", {date: root.displayLocale.toString(new Date(root.report.fetchedAt), root.displayLocale.dateTimeFormat(Locale.ShortFormat))}) + "  ·  " : "") + root.t("automaticRefresh"); font.pixelSize: Style.space(11); color: Qt.alpha(root.popupColors.text, 0.65) }
      }
    }
  }
}
