import QtQuick
import qs.Commons

Rectangle {
  id: root
  readonly property var popupColors: Color.popups
  property string text: ""
  property bool selected: false
  signal clicked()
  implicitWidth: label.implicitWidth + 22
  implicitHeight: Style.space(32)
  radius: Style.space(5)
  color: selected || mouse.containsMouse ? Qt.alpha(Color.accent, 0.16) : "transparent"
  border.width: 1
  border.color: selected ? Color.accent : Qt.alpha(root.popupColors.text, 0.22)
  activeFocusOnTab: true
  Keys.onReturnPressed: clicked()
  Keys.onSpacePressed: clicked()
  Label {
    id: label
    anchors.centerIn: parent
    text: root.text
    color: root.selected ? Color.accent : root.popupColors.text
  }
  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.clicked()
  }
}
