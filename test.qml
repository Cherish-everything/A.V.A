import QtQuick
import QtQuick.Effects
import QtQuick.Controls

Window {
    id: mainwindow
    width: 360; height: 360
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

    // Hidden base shape for the UI container and multi-effect shadow
    Rectangle {
        id: orbShape
        width: 240; height: 240
        radius: width / 2
        anchors.centerIn: parent
        color: '#74538ff6'
        border.color: "white"
        visible: false
        layer.enabled: true
    }

    MultiEffect {
        source: orbShape
        anchors.fill: orbShape
        autoPaddingEnabled: true
        shadowEnabled: false
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

    // Circular waveform visualizer
    Canvas {
        id: waveformCanvas
        width: 360; height: 360
        anchors.centerIn: parent
        
        property real targetAudioLevel: 0
        property real audioLevel: 0
        property int segments: 128
        property real baseRadius: 120
        property real maxAmplitude: 45
        property real animationTime: 0

        Behavior on audioLevel {
            NumberAnimation { duration: 100; easing.type: Easing.OutQuad }
        }

        onTargetAudioLevelChanged: {
            audioLevel = targetAudioLevel
        }

        onAudioLevelChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.save()
            ctx.translate(width / 2, height / 2)

            var level = audioLevel
            var baseR = waveformCanvas.baseRadius

            ctx.beginPath()

            if (level < 0.01) {
                ctx.arc(0, 0, baseR, 0, Math.PI * 2)
            } else {
                var segs = waveformCanvas.segments
                var maxAmp = waveformCanvas.maxAmplitude
                var animTime = waveformCanvas.animationTime * 0.002

                for (var i = 0; i <= segs; i++) {
                    var angle = (i / segs) * Math.PI * 2
                    
                    var noise1 = Math.sin(i * 0.3 + animTime * 4.0)
                    var noise2 = Math.cos(i * 0.7 - animTime * 3.0)
                    var noise3 = Math.sin(i * 1.2 + animTime * 5.5)
                    
                    var combinedNoise = (noise1 + noise2 + noise3 + 3) / 6.0
                    var spike = Math.pow(combinedNoise, 1.6) * maxAmp * Math.max(0.15, level)
                    
                    var r = baseR + spike
                    var x = Math.cos(angle) * r
                    var y = Math.sin(angle) * r
                    
                    if (i === 0) ctx.moveTo(x, y)
                    else ctx.lineTo(x, y)
                }
                ctx.closePath()
            }

            // 1. Outer soft bloom
            ctx.lineWidth = 14
            ctx.strokeStyle = "rgba(0, 136, 255, 0.15)"
            ctx.stroke()

            // 2. Mid glow layer
            ctx.lineWidth = 6
            ctx.strokeStyle = "rgba(0, 136, 255, 0.5)"
            ctx.stroke()

            // 3. Core bright line
            ctx.lineWidth = 2.5
            ctx.strokeStyle = "#FFFFFF"
            ctx.stroke()

            ctx.restore()
        }

        Timer {
            interval: 33
            running: waveformCanvas.audioLevel > 0.01
            repeat: true
            onTriggered: {
                waveformCanvas.animationTime += 33
                waveformCanvas.requestPaint()
            }
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
            height: 90
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            fontSizeMode: Text.Fit
            minimumPixelSize: 9
            font.pixelSize: 14
            elide: Text.ElideRight
            color: '#c8e6fe'
        }

        // Rounded TextField
        TextField {
            id: inputField
            anchors.horizontalCenter: parent.horizontalCenter
            width: 160
            height: 32
            color: "black"
            placeholderText: "Enter text"
            placeholderTextColor: '#6375ad'
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            
            
            background: Rectangle {
                color: '#d1d4ff'
                radius: 16
                border.width: 0
                anchors.bottomMargin: 20
            }
            
            onAccepted: mainwindow.send()
        }

        
    }

    Connections {
        target: backend
        function onReplyReady(text) { resultText.text = text }
        function onLevelChanged(level) { waveformCanvas.audioLevel = level }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: Qt.quit()
    }
}