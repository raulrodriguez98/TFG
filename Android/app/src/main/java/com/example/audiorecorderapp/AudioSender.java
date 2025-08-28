package com.example.audiorecorderapp;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.RandomAccessFile;

import okhttp3.*;

public class AudioSender {
    private static final int SAMPLE_RATE = 16000;
    private static final int CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO;
    private static final int AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT;

    private AudioRecord recorder;
    private Thread recordingThread;
    private boolean isRecording = false;

    private final String filePath;

    public AudioSender(String filePath) {
        this.filePath = filePath;
    }

    /* Inicio de grabación */
    public void startRecording() {
        int bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT);
        recorder = new AudioRecord(MediaRecorder.AudioSource.MIC, SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT, bufferSize);

        recorder.startRecording();
        isRecording = true;

        recordingThread = new Thread(() -> writeAudioDataToFile(bufferSize), "AudioRecorder Thread");
        recordingThread.start();

        Log.d("AudioRecorderWav", "Grabación iniciada");
    }

    /* Creación de archivo de audio */
    private void writeAudioDataToFile(int bufferSize) {
        byte[] data = new byte[bufferSize];
        FileOutputStream os;

        try {
            os = new FileOutputStream(filePath);
        } catch (IOException e) {
            Log.e("AudioRecorderWav", "Error al crear archivo", e);
            return;
        }

        while (isRecording) {
            int read = recorder.read(data, 0, bufferSize);
            if (read > 0) {
                try {
                    os.write(data, 0, read);
                } catch (IOException e) {
                    Log.e("AudioRecorderWav", "Error al escribir datos", e);
                }
            }
        }

        try {
            os.close();
        } catch (IOException e) {
            Log.e("AudioRecorderWav", "Error cerrando archivo", e);
        }
    }

    /* Finalización de grabación y llamada para envío a server.js */
    public void stopRecordingAndSend() {
        if (recorder == null) return;

        isRecording = false;
        recorder.stop();
        recorder.release();
        recorder = null;

        try {
            recordingThread.join();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }

        try {
            normalizeAudio(filePath);
            addWavHeader(filePath);
        } catch (IOException e) {
            Log.e("AudioRecorderWav", "Error añadiendo cabecera WAV", e);
        }

        Log.d("AudioRecorderWav", "Grabación detenida y archivo WAV creado");

        sendAudio(new File(filePath));
    }

    /* Normalizar PCM16 */
    private void normalizeAudio(String path) throws IOException {
        RandomAccessFile raf = new RandomAccessFile(path, "rw");

        // Leer PCM puro (sin cabecera)
        byte[] header = new byte[44];
        raf.seek(0);
        raf.read(header);

        int numSamples = (int) ((raf.length() - 44) / 2);
        short[] samples = new short[numSamples];

        for (int i = 0; i < numSamples; i++) {
            samples[i] = Short.reverseBytes(raf.readShort());
        }

        // Máximo absoluto
        short max = 0;
        for (short s : samples) if (Math.abs(s) > max) max = (short) Math.abs(s);

        if (max == 0) return; // evitar división por 0

        float scale = 32767f / max;

        // Escribir muestras normalizadas
        raf.seek(44);
        for (short s : samples) {
            short normalized = (short) (s * scale);
            raf.writeShort(Short.reverseBytes(normalized));
        }

        raf.close();
    }

    /* Cabecera de parámetros del archivo de audio wav */
    private void addWavHeader(String filePath) throws IOException {
        RandomAccessFile wavFile = new RandomAccessFile(filePath, "rw");

        long totalAudioLen = wavFile.length();
        long totalDataLen = totalAudioLen + 36;
        long longSampleRate = SAMPLE_RATE;
        int channels = 1;
        long byteRate = 16 * SAMPLE_RATE * channels / 8;

        wavFile.seek(0);
        wavFile.writeBytes("RIFF");
        wavFile.writeInt(Integer.reverseBytes((int) totalDataLen));
        wavFile.writeBytes("WAVE");
        wavFile.writeBytes("fmt ");
        wavFile.writeInt(Integer.reverseBytes(16));
        wavFile.writeShort(Short.reverseBytes((short) 1));
        wavFile.writeShort(Short.reverseBytes((short) channels));
        wavFile.writeInt(Integer.reverseBytes((int) longSampleRate));
        wavFile.writeInt(Integer.reverseBytes((int) byteRate));
        wavFile.writeShort(Short.reverseBytes((short) (channels * 16 / 8)));
        wavFile.writeShort(Short.reverseBytes((short) 16));
        wavFile.writeBytes("data");
        wavFile.writeInt(Integer.reverseBytes((int) totalAudioLen));

        wavFile.close();
    }

    /* Envío de archivo a server.js */
    private void sendAudio(File file) {
        OkHttpClient client = new OkHttpClient();
        RequestBody requestBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("audio", "audio.wav",
                        RequestBody.create(file, MediaType.parse("audio/wav")))
                .build();

        Request request = new Request.Builder()
                .url("http://10.0.2.2:3000/api/stt")
                .post(requestBody)
                .build();

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                Log.e("AudioSender", "Error al enviar el audio", e);
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                Log.i("AudioSender", "Audio enviado exitosamente. Código: " + response.code());
            }
        });
    }
}
