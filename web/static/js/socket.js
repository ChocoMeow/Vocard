class Socket {
    constructor(url) {
        this.url = url;
        this.socket = null;
    }

    connect(player) {
        this.socket = io.connect(this.url);

        this.socket.on('connect', () => {
            console.log("Connected to server!");
        });

        this.socket.on('disconnect', () => {
            player.init();
            console.log("Disconnected from server!");
        });

        this.socket.on('error', (e) => {
            console.log(e);
        })
    }

    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }

    send(msg) {
        if (this.socket) {
            this.socket.emit('message', msg);
        }
    }

    addMessageListener(callback) {
        if (this.socket) {
            this.socket.on('message', callback);
        }
    }

    removeMessageListener(callback) {
        if (this.socket) {
            this.socket.off('message', callback);
        }
    }
}