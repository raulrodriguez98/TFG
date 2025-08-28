const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const cors = require('cors');
const axios = require('axios');
const { SpeechClient } = require('@google-cloud/speech'); // Importa el cliente de Speech-to-Text
const textToSpeech = require('@google-cloud/text-to-speech'); // Importa el cliente de Text-to-Speech

const app = express();
const port = 3000;

// Configuración de Google Cloud Speech-to-Text
// La librería buscará automáticamente la variable de entorno GOOGLE_APPLICATION_CREDENTIALS
const speechClient = new SpeechClient();

const clienteTTS = new textToSpeech.TextToSpeechClient();

// Variable global para guardar la última respuesta que ha dado el Chatbot
let ultimaRespuesta = "";

// Configuración de CORS para permitir peticiones desde otros orígenes
app.use(cors());
app.use(express.json());

// Directorio para almacenar temporalmente el audio
const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) {
    fs.mkdirSync(uploadsDir);
}

// Configuración de multer para guardar el archivo de audio de forma temporal
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadsDir);
    },
    filename: (req, file, cb) => {
        cb(null, 'audio.wav');
    }
});
const upload = multer({ storage: storage });


// Endpoint POST para recibir el audio desde la app Android
app.post('/api/stt', upload.single('audio'), (req, res) => {
    if (!req.file) {
        console.error("No se recibió ningún archivo de audio en POST /api/stt.");
        return res.status(400).send("No se recibió ningún archivo de audio.");
    }
    console.log('Audio recibido de la app Android y guardado como audio.wav:', req.file.originalname);
    console.log('Tamaño:', req.file.size);
    res.status(200).send("Audio recibido y guardado temporalmente.");
});


// Endpoint GET para que la página web reciba el audio para reproducción
app.get('/api/stt', (req, res) => {
    const audioPath = path.join(uploadsDir, 'audio.wav');
    if (fs.existsSync(audioPath)) {
        console.log("Sirviendo audio.wav para reproducción.");
        res.sendFile(audioPath, (err) => {
            if (err) {
                console.error("Error al enviar el audio para reproducción:", err);
                res.status(500).send("Error al servir el archivo de audio.");
            } else {
                console.log("Audio enviado para reproducción.");
            }
        });
    } else {
        console.log("No se encontró 'audio.wav' en /uploads para servir.");
        res.status(404).send("No se encontró audio en el servidor para reproducir.");
    }
});


// Endpoint GET para que la página web inicie la transcripción
// Este endpoint lee el audio ya guardado y lo envía a Google STT.
app.get('/api/transcribe', async (req, res) => {
    const audioPath = path.join(uploadsDir, 'audio.wav');

    // 1. Verificar si el archivo de audio existe
    if (!fs.existsSync(audioPath)) {
        console.log("Error: No se encontró el archivo 'audio.wav' para transcribir.");
        return res.status(404).json({ error: "No se encontró audio para transcribir. Asegúrate de que la app Android lo haya enviado previamente." });
    }

    // 2. Leer el archivo de audio
    let audioBuffer;
    try {
        audioBuffer = fs.readFileSync(audioPath);
    } catch (readError) {
        console.error("Error al leer el archivo de audio:", readError);
        return res.status(500).json({ error: "Error interno al leer el archivo de audio.", details: readError.message });
    }

    // 3. Configurar la solicitud a Google Cloud Speech-to-Text
    const request = {
        audio: {
            content: audioBuffer.toString('base64'), // Convierte el buffer a Base64
        },
        config: {
            encoding: 'LINEAR16',
            sampleRateHertz: 16000,
            languageCode: 'es-ES',
            // Parámetro opcionales para frases más largas o contextos específicos
            // enableAutomaticPunctuation: true,
            // model: 'default' // o 'command_and_search', 'phone_call', 'video'
            model: 'default', // ha dado mejores resultados, no se come tantas palabras
            useEnhanced: 'true'
        },
    };

    let transcription = "No se pudo transcribir el audio (sin resultados).";
    try {
        // 4. Realizar la transcripción con Google Speech-to-Text
        console.log("Iniciando transcripción con Google Speech-to-Text...");
        const [response] = await speechClient.recognize(request);

        if (response.results && response.results.length > 0) {
            transcription = response.results
                .map(result => result.alternatives[0].transcript)
                .join('\n');
            console.log(`Transcripción exitosa: ${transcription}`);
        } else {
            console.log("No se obtuvieron resultados de transcripción de Google.");
            transcription = "No se pudo transcribir el audio (sin resultados).";
        }

        // 5. Borrar audio después de transcribir
        fs.unlink(audioPath, (err) => {
            if (err) console.error("Error al eliminar audio tras transcribir:", err);
        });

        // 6. Enviar la transcripción de vuelta al frontend y el chatbot
        res.status(200).json({ transcript: transcription });

    } catch (error) {
        console.error('Error al llamar a Google Speech-to-Text:', error);
        // Si hay un error de Google, lo enviamos al frontend y registramos detalles.
        res.status(500).json({
            error: 'Error al transcribir el audio con Google Speech-to-Text.',
            details: error.message,
            googleErrorResponse: error.details || error.stack // Para errores más específicos de la API de Google
        });
    }
});


// Endpoint para comunicar a Python que hay una nueva interacción del usuario
app.get('/api/check-interaction', (req, res) => {
    const audioPath = path.join(uploadsDir, 'audio.wav');
    
    // 1. Verificar si existe el archivo
    if (!fs.existsSync(audioPath)) {
        return res.json({ status: 'no_audio' });
    }
    
    // 2. Verificar si es reciente (< 30 segundos)
    const stats = fs.statSync(audioPath);
    const ahora = Date.now();
    const modificadoHace = ahora - stats.mtimeMs;
    const esReciente = modificadoHace < 30000;  // 30 segundos
    
    res.json({
        status: esReciente ? 'has_audio' : 'stale_audio',
        lastModified: stats.mtime
    });
});


// Endpoint para recibir la respuesta del chatbot desde script
app.post('/api/respuesta-chatbot', (req, res) => {
    const { texto } = req.body;

    if(!texto || texto.trim() === ""){
        return res.status(400).send("Repuesta vacía.");
    }

    ultimaRespuesta = texto.trim();
    console.log("Respuesta recibida del Chatbot: ", ultimaRespuesta);
    res.status(200).send("Respuesta recibida con éxito.");
});


// También se hace el TTS de la respuesta
app.get('/api/tts', async (req, res) => {
    if (!ultimaRespuesta) {
        return res.status(404).send("La respuesta no tiene contenido o texto para convertir.");
    }

    try {
        const request = {
            input: { text: ultimaRespuesta },
            voice: {
                languageCode: 'es-ES',
                ssmlGender: 'NEUTRAL',
            },
            audioConfig: { audioEncoding: 'MP3' },
        };

        const [response] = await clienteTTS.synthesizeSpeech(request);

        res.set({
            'Content-Type': 'audio/mpeg',
            'Content-Disposition': 'inline; filename="respuesta.mp3"',
        });

        res.send(response.audioContent);
    } catch (err) {
        console.error("Error ejecutando TTS: ", err);
        res.status(500).send("Error al generar el audio.");
    }
});


app.listen(port, () => {
    console.log(`Servidor Node.js corriendo en http://localhost:${port}`);
    console.log(`¡Recuerda configurar GOOGLE_APPLICATION_CREDENTIALS con la ruta a tu clave de servicio!`);
});
