package com.example.audiorecorderapp

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private val REQUEST_RECORD_AUDIO_PERMISSION = 200
    private lateinit var audioSender: AudioSender

    /* Botones de la aplicación */
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        requestPermissions()

        val filePath = filesDir.absolutePath + "/audio.wav"
        audioSender = AudioSender(filePath)

        val startButton: Button = findViewById(R.id.startButton)
        val stopButton: Button = findViewById(R.id.stopButton)

        startButton.setOnClickListener {
            try {
                audioSender.startRecording()
                Toast.makeText(this, "Grabando...", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                e.printStackTrace()
                Toast.makeText(this, "Error al iniciar grabación", Toast.LENGTH_SHORT).show()
            }
        }

        stopButton.setOnClickListener {
            audioSender.stopRecordingAndSend()
            Toast.makeText(this, "Grabación detenida y enviada", Toast.LENGTH_SHORT).show()
        }
    }

    /* Petición de permisos para poder grabar o acceder al micro y conectarse al servidor */
    private fun requestPermissions() {
        val permissions = arrayOf(
            Manifest.permission.RECORD_AUDIO
        )

        val allGranted = permissions.all {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }

        if (!allGranted) {
            ActivityCompat.requestPermissions(this, permissions, REQUEST_RECORD_AUDIO_PERMISSION)
        }
    }

    /* Comprobación permisos concedidos */
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        if (requestCode == REQUEST_RECORD_AUDIO_PERMISSION) {
            if (grantResults.any { it != PackageManager.PERMISSION_GRANTED }) {
                Toast.makeText(
                    this,
                    "Se requieren todos los permisos para grabar audio",
                    Toast.LENGTH_LONG
                ).show()
                finish()
            } else {
                Toast.makeText(this, "Permisos concedidos", Toast.LENGTH_SHORT).show()
            }
        }
    }
}
