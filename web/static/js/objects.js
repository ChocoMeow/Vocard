class Timer {
    constructor(callback, interval) {
        this.callback = callback;
        this.interval = interval;
        this.timerId = null;
        this.isRunning = false;
    }

    start() {
        if (!this.isRunning) {
            this.isRunning = true;
            this.timerId = setInterval(() => {
                this.callback();
            }, this.interval);
        }
    }

    stop() {
        if (this.isRunning) {
            clearInterval(this.timerId);
            this.timerId = null;
            this.isRunning = false;
        }
    }

    getIsRunning() {
        return this.isRunning;
    }
}

class DataInput {
    #pos = 0;
    #buf = Uint8Array;
    #view = DataView;

    constructor(bytes) {
        if (typeof bytes === "string") {
            const decodedString = atob(bytes);
            const byteArr = new Uint8Array(decodedString.length);
            for (let i = 0; i < decodedString.length; i++) {
                byteArr[i] = decodedString.charCodeAt(i);
            }
            bytes = byteArr;
        }
        this.#buf = bytes;
        this.#view = new DataView(bytes.buffer);
    }

    #_advance(bytes) {
        if (this.#pos + bytes > this.#buf.length) {
            throw new Error("Buffer overflow: cannot advance further.");
        }
        const p = this.#pos;
        this.#pos += bytes;
        return p;
    }

    readByte() {
        return this.#buf[this.#_advance(1)];
    }

    readBoolean() {
        return this.readByte() !== 0;
    }

    readUnsignedShort() {
        return this.#view.getUint16(this.#_advance(2), false);
    }

    readInt() {
        return this.#view.getInt32(this.#_advance(4), false);
    }

    readLong() {
        const msb = this.#view.getInt32(this.#_advance(4), false);
        const lsb = this.#view.getUint32(this.#_advance(4), false);
        return BigInt(msb) << 32n | BigInt(lsb);
    }

    readUTF() {
        const len = this.readUnsignedShort();
        const start = this.#_advance(len);
        return new window.TextDecoder().decode(this.#buf.slice(start, start + len));
    }
}

class Track {
    constructor(object) {
        this.title = object.title;
        this.author = object.author;
        this.source = object.source;
        this.identifier = object.identifier;
        if (object.thumbnail == undefined) {
            if (this.source == "youtube") {
                this.imageUrl = `https://img.youtube.com/vi/${this.identifier}/hqdefault.jpg`
            } else {
                this.imageUrl = "https://cdn.discordapp.com/attachments/674788144931012638/823086668445384704/eq-dribbble.gif";
            }
        } else {
            this.imageUrl = object.thumbnail;
        }
        this.isStream = object.isStream;
        this.length = Number(object.length);
        this.track_id = object.track_id;
        this.uri = object.uri;
    }
}

const decoders = [
    (input, track_id) => {
        const title = input.readUTF();
        const author = input.readUTF();
        const length = input.readLong();
        const identifier = input.readUTF();
        const isStream = input.readBoolean();
        const uri = input.readBoolean() ? input.readUTF() : null;
        const thumbnail = input.readBoolean() ? input.readUTF() : null;
        const source = input.readUTF();

        return { track_id, title, author, length, identifier, isStream, uri, thumbnail, source, position: 0n };
    },
    undefined,
    (input, track_id) => {
        const title = input.readUTF();
        const author = input.readUTF();
        const length = input.readLong();
        const identifier = input.readUTF();
        const isStream = input.readBoolean();
        const uri = input.readBoolean() ? input.readUTF() : null;
        const source = input.readUTF();

        return { track_id, title, author, length, identifier, isStream, uri, thumbnail: null, source, position: 0n };
    },
    (input, track_id) => {
        const title = input.readUTF();
        const author = input.readUTF();
        const length = input.readLong();
        const identifier = input.readUTF();
        const isStream = input.readBoolean();
        const uri = input.readBoolean() ? input.readUTF() : null;
        const thumbnail = input.readBoolean() ? input.readUTF() : null;
        const isrc = input.readBoolean() ? input.readUTF() : null;
        const source = input.readUTF();

        return { track_id, title, author, length, identifier, isStream, uri, thumbnail, source, position: 0n };
    }
]
function decode(track_id) {
    const input = new DataInput(track_id);
    const flags = input.readInt();
    const version = input.readByte();

    const decoder = decoders[version];
    return new Track(decoder(input, track_id));
}

const actions = {
    initPlayer: function (player, data) {
        player.init();
        player.isDJ = data['is_dj'];
        player.addTrack(data["tracks"]);
        player.updateCurrentQueuePos(data['current_queue_position']);
        player.is_paused = data['is_paused'];
        player.current_position = data['current_position'];
        player.repeat = data['repeat_mode'];
        player.channelName = data["channel_name"];
        player.autoplay = data["autoplay"];
        data["users"].forEach(user => {
            player.addUser(user);
        })

        $("#sortable").sortable("option", "disabled", !player.isDJ);
    },

    playerUpdate: function (player, data) {
        player.last_update = data["last_update"];
        player.is_connected = data["is_connected"];
        player.current_position = data["last_position"];
    },

    trackUpdate: function (player, data) {
        let track = player.updateCurrentQueuePos(data['current_queue_position']);
        player.is_paused = data['is_paused'];
        if (track?.track_id != data["track_id"]) {
            player.send({ "op": "initPlayer" })
        }
    },

    addTrack: function (player, data) {
        player.addTrack(data["tracks"]);
        var tracks = data["tracks"];
        if (tracks.length == 1) {
            var msg = `Added ${decode(tracks[0]).title} songs into the queue.`
        } else {
            var msg = `Added ${tracks.length} into the queue.`
        }
        player.showToast(data["requester_id"], msg)
    },

    getTracks: function (player, data) {
        let tracks = data["tracks"];
        if (tracks != undefined) {
            const resultList = $("#search-result-list");
            resultList.empty();
            player.searchList = tracks;
            for (let i in tracks) {
                let track = decode(tracks[i])
                resultList.append(`<li class="search-result"><div class="search-result-left"><img src=${track.imageUrl} /><div class="search-result-info"><p class="info">${track.title}</p><p class="desc">${track.author}</p></div></div><p>${player.msToReadableTime(track.length)}</p></li>`)
            }
        }
        $("#search-result-list").fadeIn(200);
        $("#search-loader").fadeOut(200);
    },

    playerClose: function (player, data) {
        player.init();
    },

    updateGuild: function (player, data) {
        const user = data["user"];
        player.channelName = data["channel_name"];

        if (user["user_id"] == player.userId) {
            if (data['is_joined']) {
                player.send({ "op": "initPlayer" });
            } else {
                player.init();
            }
        }
        if (data['is_joined']) {
            player.addUser(user);
            if (user["user_id"] != player.userId) {
                player.showToast(user["user_id"], "Joined your channel!");
            }
        } else {
            if (player.users.hasOwnProperty(user["user_id"])) {
                player.showToast(user["user_id"], "Left your channel!");
                delete player.users[user['user_id']];
                player.updateUser();
            }
        }
    },

    updatePause: function (player, data) {
        player.is_paused = data['pause'];
        if (data["pause"]) {
            var msg = "Paused the player."
        } else {
            var msg = "Resumed the player."
        }
        player.showToast(data["requester_id"], msg)
    },

    updatePosition: function (player, data) {
        player.current_position = data["position"];
    },

    swapTrack: function (player, data) {
        let index1 = player.current_queue_position + data['position2']["index"];
        let index2 = player.current_queue_position + data['position1']["index"];
        let track1 = player.queue[index1];
        let track2 = player.queue[index2];

        if (track1?.track_id != data['position1']["track_id"] || track2?.track_id != data['position2']["track_id"]) {
            return player.send({ "op": "initPlayer" });
        }

        player.queue[index1] = player.queue.splice(index2, 1, player.queue[index1])[0];
        player.initSortable();
        player.showToast(data["requester_id"], `${track1.title} and ${track2.title} are swapped`)
    },

    moveTrack: function (player, data) {
        let position = player.current_queue_position + data["position"]["index"];
        let newPosition = player.current_queue_position + data["newPosition"]["index"];
        let element = player.queue.splice(position, 1)[0];
        if (element?.track_id != data["position"]["track_id"]) {
            return player.send({ "op": "initPlayer" });
        }
        player.queue.splice(newPosition, 0, element);

        const $ul = $('#sortable');
        const $li = $ul.children().eq(position);
        $li.detach();
        $ul.children().eq(newPosition).before($li);
        player.showToast(data["requester_id"], `Moved ${element.title} to ${newPosition}`)
    },

    shuffleTrack: function (player, data) {
        let tracks = data["tracks"];
        if (tracks != undefined) {
            player.queue = [];
            tracks.forEach(rawTrack => {
                let track = new Track(rawTrack);
                player.queue.push(track);
            });
            player.initSortable();
            player.showToast(data["requester_id"], "The queue is shuffled.")
        }
    },

    repeatTrack: function (player, data) {
        player.repeat = data["repeatMode"];
    },

    removeTrack: function (player, data) {
        const positions = data["positions"];
        const trackIds = data["track_ids"];
        var removeTracks = []
        var newQueue = [];

        player.queue.forEach((track, index) => {
            if (positions.includes(index)) {
                if (trackIds.includes(track.track_id)) {
                    if (index < player.current_queue_position) {
                        player.current_queue_position -= 1;
                    }
                    removeTracks.push(track);
                } else {
                    return player.send({ "op": "initPlayer" })
                }
            } else {
                newQueue.push(track);
            }
        })

        player.queue = newQueue;
        player.initSortable();

        if (removeTracks.length == 1) {
            var msg = `Removed ${removeTracks[0].title} from the queue.`;
        } else {
            var msg = `Removed ${removeTracks.length} tracks from the queue.`;
        }

        player.showToast(data["requester_id"], msg);
    },

    toggleAutoplay: function (player, data) {
        var status = data["status"];
        player.autoplay = status;
    },

    errorMsg: function (player, data) {
        player.showToast(data["level"], data["msg"]);
    },

    getPlaylists: function (player, data) {
        const playlists = data["playlists"]
        player.playlists = playlists;
        player.updatePlaylists();
    }
}

class Player {
    constructor(userId) {
        this.socket = new Socket(`${window.location.protocol}//${window.location.hostname}:${window.location.port}`);
        this.socket.connect(this);
        this.socket.addMessageListener((msg) => this.handleMessage(msg));
        this.timer = new Timer(() => this.updateTime(), 1000);
        this.userId = parseInt(userId);
        this.isDJ = false;
        this.date = new Date();
        this.queue = [];
        this.users = {};
        this.searchList = [];
        this.repeat = "off";
        this.currentTrack = null;
        this.current_queue_position = 0;
        this.current_position = 0;
        this.is_paused = false;
        this.volume = 100;
        this.last_update = 0;
        this.is_connected = true;
        this.autoplay = false;

        this.channelName = "";
        this.playlists = null;
    }

    handleMessage(data) {
        const op = data["op"];
        const validActions = Object.keys(actions);

        if (validActions.includes(op)) {
            actions[op](this, data);
        } else {
            console.log(`Invalid action: ${op}`)
        }

        return this.updateInfo()
    }

    init() {
        this.queue = []
        this.currentTrack = null;
        this.users = [];
        $('#sortable').empty();
        this.updateInfo();
    }

    initSortable() {
        $('#sortable').empty();
        for (var i in this.queue) {
            var track = this.queue[i];
            $("#sortable").append(`<li><div class="track"><div class="left">${(this.isDJ) ? '<i class="fa-solid fa-bars handle"></i>' : ''}<img src=${track.imageUrl} /><div class="info"><p>${track.title}</p><p class="desc">${track.author}</p></div></div><p class="time">${this.msToReadableTime(track.length)}</p><i class="fa-solid fa-ellipsis-vertical action"></i></div></li>`)
        }
        this.updateCurrentQueuePos();
    }

    updateCurrentQueuePos(pos) {
        if (pos != undefined) {
            this.current_queue_position = pos - 1;
        }
        this.currentTrack = this.queue[this.current_queue_position];

        $('#sortable li div').removeClass('active');
        const li = $(`#sortable li:eq(${this.current_queue_position})`);
        li.find('div').addClass('active');

        const queue = $('.queue-list')
        if (queue.prop('scrollHeight') > queue.prop('clientHeight')) {
            queue.animate({ scrollTop: li.position().top - queue.position().top }, 'slow');
        }
        return this.currentTrack;
    }

    addUser(user) {
        this.users[user['user_id']] = { avatar_url: user["avatar_url"], name: user["name"] };
        this.updateUser();
    }

    updateUser() {
        $("#users-container").empty();
        for (const [id, user] of Object.entries(this.users)) {
            $("#users-container").append(`<li class="user"><div class="left"><img src=${user.avatar_url} /><p>${user.name}</p></div><i class="fa-solid fa-microphone"></i></li>`)
        };
    }
    addTrack(tracks) {
        for (let i in tracks) {
            let track = decode(tracks[i])
            this.queue.push(track);
            $("#sortable").append(`<li><div class="track"><div class="left">${(this.isDJ) ? '<i class="fa-solid fa-bars handle"></i>' : ''}<img src=${track.imageUrl} /><div class="info"><p>${track.title}</p><p class="desc">${track.author}</p></div></div><p class="time">${this.msToReadableTime(track.length)}</p><i class="fa-solid fa-ellipsis-vertical action"></i></div></li>`)
        }
    }

    moveTrack(target, to) {
        const c = this.current_queue_position;
        let element = this.queue.splice(target, 1)[0];
        this.queue.splice(to, 0, element);

        const $ul = $('#sortable');
        const $li = $ul.children().eq(position);
        $li.detach();
        $ul.children().eq(to).before($li);

        if (target > c && to <= c) {
            this.current_queue_position += 1;
        } else if (target < c && to >= c) {
            this.current_queue_position -= 1;
        } else if (target == c) {
            this.current_queue_position = to;
        }

        this.send({ "op": "moveTrack", "position": target, "newPosition": to })
    }

    removeTrack(position, track) {
        let rawTrack = this.queue[position];
        if (position == this.current_queue_position) {
            return this.showToast("error", "You are not allow to remove playing track!");
        }
        if (rawTrack.track_id == track.track_id) {
            this.send({ "op": "removeTrack", "position": position, "track_id": track.track_id });
        } else {
            this.showToast("error", "Track not found!");
        }
    }

    togglePause() {
        this.send({ "op": "updatePause", "pause": !this.is_paused });
    }

    skipTo(index = 1) {
        this.send({ "op": "skipTo", "index": index });
    }

    backTo(index = 1) {
        this.send({ "op": "backTo", "index": index });
    }

    seekTo(tempPosition) {
        if (this.currentTrack == undefined) {
            return;
        }
        let position = tempPosition / 500 * this.currentTrack.length;
        this.send({ "op": "updatePosition", "position": Math.trunc(position) });
    }

    shuffle() {
        if ((this.queue.length - this.current_queue_position) > 3) {
            this.send({ "op": "shuffleTrack" });
        } else {
            this.showToast("info", "Add more songs to the queue before shuffling.");
        }
    }

    repeatMode() {
        this.send({ "op": "repeatTrack" })
    }

    send(payload) {
        let json = JSON.stringify(payload)
        this.socket.send(json);
    }

    isPlaying() {
        return (this.currentTrack != undefined && this.is_connected);
    }

    msToReadableTime(ms) {
        let totalSeconds = Math.floor(ms / 1000);

        let hours = Math.floor(totalSeconds / 3600);
        let minutes = Math.floor((totalSeconds % 3600) / 60);
        let seconds = totalSeconds % 60;

        minutes = (minutes < 10) ? "0" + minutes : minutes;
        seconds = (seconds < 10) ? "0" + seconds : seconds;

        let timeString = "";
        if (hours > 0) {
            timeString += hours + ":" + minutes + ":" + seconds;
        } else {
            timeString += minutes + ":" + seconds;
        }

        return timeString;
    }

    showToast(userId, msg) {
        if (userId == "info") {
            var user = { avatar_url: "/static/img/info.png", name: "Info" }
        } else if (userId == "error") {
            var user = { avatar_url: "/static/img/error.png", name: "Error" }
        } else {
            var user = this.users[userId];
        }
        if (user != null) {
            let $element = $(`<div class="toast"><img src=${user['avatar_url']} alt="user-icon"/><div class="content"><p class="username">${user['name']}</p><p class="message">${msg}</p></div></div>`)
            $(".toastContrainer").append($element)

            setTimeout(function () {
                $element.fadeOut(500, function () {
                    $(this).remove();
                });
            }, 6000);
        }
    }

    updateTime() {
        if (this.currentTrack == undefined) {
            return this.timer.stop();
        }

        if (this.current_position >= this.currentTrack?.length) {
            return this.timer.stop();
        }
        this.current_position += 1000;
        $("#position").text(this.msToReadableTime(this.current_position));

        let time = (this.current_position / this.currentTrack?.length) * 500;
        $("#seek-bar").val(time);
    }

    updateInfo() {
        let currentTrack = this.currentTrack;
        if (currentTrack == undefined) {
            $("#title").text("");
            $("#author").text("");
            $("#position").text("00:00");
            $("#length").text("00:00");
            $("#image").fadeOut(100, function () { $(this).removeAttr("src"); });
            $("#largeImage").fadeOut(100, function () { $(this).removeAttr("src"); });
            $(".thumbnail-background").fadeOut(200);

        } else {
            $("#title").text(currentTrack.title);
            $("#author").text(currentTrack.author);
            $("#length").text(this.msToReadableTime(currentTrack.length));
            $("#auto-play").prop('checked', this.autoplay);

            let image = "";
            if (currentTrack.source == "youtube") {
                image += `${window.location.protocol}//${window.location.hostname}:${window.location.port}/`;
            }
            image += currentTrack.imageUrl;

            if ($("#largeImage").attr("src") != image) {
                $(".thumbnail-background").fadeOut(100);
                $("#largeImage").fadeOut(function () {
                    $(this).attr("src", image);

                });
                $("#image").fadeOut(function () {
                    $(this).attr("src", currentTrack.imageUrl);
                });

                if (this.playlists != null) {
                    if (this.playlists["200"]["tracks"].includes(currentTrack.track_id)) {
                        $("#like-btn").removeClass("fa-regular").addClass("fa-solid");
                    } else {
                        $("#like-btn").removeClass("fa-solid").addClass("fa-regular");
                    }
                }
            }
        }

        $("#channel-name").text((this.channelName == "") ? "Not Found" : this.channelName);
        let play_pause_btn = $("#play-pause-btn");
        let repeat_btn = $("#repeat-btn");
        if (this.is_paused || currentTrack == undefined) {
            play_pause_btn.removeClass('fa-pause').addClass('fa-play');
            if (this.timer.getIsRunning()) {
                this.timer.stop();
            }
        } else {
            play_pause_btn.removeClass('fa-play').addClass('fa-pause');
            this.timer.start();
        }

        repeat_btn.removeClass("fa-repeat-1").addClass("fa-repeat")
        if (this.repeat == "off") {
            repeat_btn.css('color', '');
        } else if (this.repeat == "track") {
            repeat_btn.css('color', '#fff');
        } else {
            repeat_btn.removeClass("fa-repeat").addClass("fa-repeat-1");
        }
    }

    updatePlaylists() {
        $("#playlists-grid").empty();
        for (let key in this.playlists) {
            const pList = this.playlists[key];
            let pDiv = $(`<div class="playlist" data-value="${key}">`);
            let iDiv = $("<div class='images'>");
            let infoDiv = $("<div class='info'>");

            if (pList["tracks"] === 0) {
                continue;
            } else {
                for (let i = 0; i < 4; i++) {
                    if (pList["tracks"][i] == undefined) {
                        continue;
                    }
                    let track = decode(pList["tracks"][i])
                    let img = $("<img>").attr("src", track.imageUrl);
                    iDiv.append(img);

                }
            }
            iDiv.append(`<i class="fa-solid fa-ellipsis-vertical action"></i>`);
            iDiv.append(`<i class="fa-solid fa-play play"></i>`);
            pDiv.append(iDiv);
            infoDiv.append(`<p>${pList["name"]}</p>`);
            infoDiv.append(`<p class="desc">${pList["type"]} • ${pList["tracks"].length} Tracks</p>`);
            pDiv.append(infoDiv);
            $("#playlists-grid").append(pDiv);
            $("#playlists-tracks").empty()
        }
    }
}