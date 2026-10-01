import QtQuick
import qs.Commons

Text {
  id: root
  readonly property var popupColors: Color.popups
  readonly property var themeFont: Style.font
  textFormat: Text.PlainText
  color: root.popupColors.text
  font.family: root.themeFont.family
  font.pixelSize: root.themeFont.body
  wrapMode: Text.WordWrap
}
