import QtQuick
import QtQuick.Effects
import QtQuick.Controls

Window {
    id: mainwindow
    width: 300; height: 300
    visible: true
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

    function send() {
            var text = inputField.text
            if (text.trim() === "") return
            inputField.text = ""
            resultText.text = "thinking..."
            backend.process_data(text)
        }

        Rectangle {
            id: orbShape
            width: 240; height: 240
            radius: width / 2
            anchors.centerIn: parent
            color: "#457568ff"
            border.color: "white"
            visible: false
            layer.enabled: true
        }

        MultiEffect {
            source: orbShape
            anchors.fill: orbShape
            autoPaddingEnabled: true
            shadowEnabled: true
            shadowColor: "#7568ff"
            shadowBlur: 1.0
            shadowScale: 1.1
            shadowOpacity: 1.0
        }

        Item {
            anchors.fill: orbShape
            DragHandler {
                target: null
                onActiveChanged: if (active) mainwindow.startSystemMove()
            }
        }
        
        Column {
            anchors.centerIn: orbShape
            spacing: 8

            Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "A.V.A v2.0"
            font.pixelSize: 15; font.bold: true
            color: "white"
            }
            
            Text {
                id: resultText
                anchors.horizontalCenter: parent.horizontalCenter
                width: 170
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 12
                color: "#94cdfc"
            }
            TextField {
                id: inputField
                anchors.horizontalCenter: parent.horizontalCenter
                width: 150
                placeholderText: "Enter text"
                onAccepted: mainwindow.send()      // Enter key sends too
            }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 8
                Button {
                    text: "Send"
                    onClicked: mainwindow.send()
                    palette.buttonText: "#000000"
                }
            }
        }

    Connections {
        target: backend
        function onReplyReady(text) { resultText.text = text }
        function onStatusChanged(message) { console.log("Notification from Python: " + message) }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: Qt.quit()
    }
}