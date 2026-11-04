import QtQuick
import QtQuick.Effects
import QtQuick.Controls

Window {
    id: mainwindow
    width: 300; height: 300
    visible: true
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

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
            anchors.horizontalCenter: parent.horizontalCenter
            text: backend.user_data
            font.pixelSize: 16
            color: "white"
        }
        TextField {
            id: inputField
            anchors.horizontalCenter: parent.horizontalCenter
            width: 150
            placeholderText: "Enter text"
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8
            Button {
                text: "Send"
                onClicked: {
                    backend.user_data = inputField.text
                    inputField.text = ""
                }
            }
            Button {
                text: "Process"
                onClicked: resultText.text = backend.process_data(inputField.text)
            }
        }
        Text {
            id: resultText
            anchors.horizontalCenter: parent.horizontalCenter
            color: "#9fd4ff"
        }
    }

    Connections {
        target: backend
        function onStatusChanged(message) {
            console.log("Notification from Python: " + message)
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: Qt.quit()
    }
}