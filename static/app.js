// WebRTC клиент
let localStream;
let remoteStream;
let peerConnection;
let screenStream;

const servers = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
    ]
};

const startBtn = document.getElementById('startBtn');
const hangupBtn = document.getElementById('hangupBtn');
const toggleVideo = document.getElementById('toggleVideo');
const toggleAudio = document.getElementById('toggleAudio');
const screenShare = document.getElementById('screenShare');
const remoteControl = document.getElementById('remoteControl');
const localVideo = document.getElementById('localVideo');
const remoteVideo = document.getElementById('remoteVideo');
const status = document.getElementById('status');

// Получаем доступ к камере/микрофону
async function init() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true
        });
        localVideo.srcObject = localStream;
        status.textContent = 'Камера и микрофон готовы';
    } catch (err) {
        status.textContent = 'Ошибка доступа к медиа: ' + err.message;
    }
}

// Начать звонок
startBtn.onclick = async () => {
    startBtn.disabled = true;
    hangupBtn.disabled = false;
    
    peerConnection = new RTCPeerConnection(servers);
    
    // Добавляем локальный поток
    localStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, localStream);
    });
    
    // Получаем удаленный поток
    peerConnection.ontrack = event => {
        remoteStream = event.streams[0];
        remoteVideo.srcObject = remoteStream;
    };
    
    // Создаем offer
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    
    status.textContent = 'Звонок начат...';
    
    // Здесь будет отправка offer на сервер
    console.log('Offer создан:', offer);
};

// Завершить звонок
hangupBtn.onclick = () => {
    if (peerConnection) {
        peerConnection.close();
        peerConnection = null;
    }
    if (remoteVideo.srcObject) {
        remoteVideo.srcObject.getTracks().forEach(track => track.stop());
        remoteVideo.srcObject = null;
    }
    startBtn.disabled = false;
    hangupBtn.disabled = true;
    status.textContent = 'Звонок завершен';
};

// Включить/выключить камеру
toggleVideo.onclick = () => {
    const videoTrack = localStream.getVideoTracks()[0];
    if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled;
        toggleVideo.textContent = videoTrack.enabled ? '📹 Выкл камеру' : '📹 Вкл камеру';
    }
};

// Включить/выключить микрофон
toggleAudio.onclick = () => {
    const audioTrack = localStream.getAudioTracks()[0];
    if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        toggleAudio.textContent = audioTrack.enabled ? '🎤 Выкл микрофон' : '🎤 Вкл микрофон';
    }
};

// Демонстрация экрана
screenShare.onclick = async () => {
    try {
        screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: true
        });
        
        const screenTrack = screenStream.getVideoTracks()[0];
        const sender = peerConnection.getSenders().find(s => s.track.kind === 'video');
        
        if (sender) {
            sender.replaceTrack(screenTrack);
        }
        
        localVideo.srcObject = screenStream;
        status.textContent = 'Демонстрация экрана активна';
        
        // Когда демонстрация закончится
        screenTrack.onended = () => {
            const originalTrack = localStream.getVideoTracks()[0];
            if (sender && originalTrack) {
                sender.replaceTrack(originalTrack);
            }
            localVideo.srcObject = localStream;
            status.textContent = 'Демонстрация экрана завершена';
        };
    } catch (err) {
        status.textContent = 'Ошибка демонстрации экрана: ' + err.message;
    }
};

// Удаленное управление (заглушка)
remoteControl.onclick = () => {
    status.textContent = 'Функция удаленного управления будет добавлена позже';
    alert('Для удаленного управления нужен WebRTC Data Channel и специальный сервер');
};

// Инициализация при загрузке
init();
