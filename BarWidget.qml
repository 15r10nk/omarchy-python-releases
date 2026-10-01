import QtQuick
import qs.Ui as Ui

Ui.BarWidget {
  id: root
  moduleName: "frank.python-releases"

  readonly property Panel panel: panelLoader.item as Panel
  readonly property bool opened: root.panel ? root.panel.opened : false
  readonly property bool popoutSwitchClosing: root.panel ? root.panel.popoutSwitchClosing : false

  function open() { if (root.panel) root.panel.open() }
  function close() { if (root.panel) root.panel.close() }
  function toggle() { if (root.panel) root.panel.toggle() }
  function closeForPopoutSwitch() { if (root.panel) root.panel.closeForPopoutSwitch() }

  function injectPanel() {
    if (!root.panel) return
    root.panel.bar = root.bar
    root.panel.settings = root.settings
    root.panel.anchorItem = button
    root.panel.hostWidget = root
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  Ui.WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.panel ? root.panel.barLabel : " …"
    tooltipText: root.panel ? root.panel.barTooltip : ""
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton || buttonCode === Qt.MiddleButton) {
        if (root.panel) root.panel.refresh(true)
      } else if (buttonCode === Qt.LeftButton) root.toggle()
    }
  }
}
