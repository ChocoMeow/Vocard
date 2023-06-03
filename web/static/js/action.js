$(document).ready(function () {
    const player = new Player(userId);
    const largeImage = document.getElementById("largeImage");
    const img = document.getElementById("image");
    const canvas = document.createElement('canvas');
    const $positionInfo = $('.position-info');

    var startPos = null;
    var selectedTrack = null;
    var selectedPlaylistId = null;
    var selectedPlaylistTrack = null;

    var typingTimer;
    var doneTypingInterval = 2000;

    largeImage.crossOrigin = "Anonymous";
    largeImage.onload = function () {
        try {
            const context = canvas.getContext('2d', { willReadFrequently: true });
            const width = canvas.width = largeImage.width;
            const height = canvas.height = Math.round(largeImage.height * 0.7);
            const startY = Math.round((largeImage.height - height) / 2);
            context.drawImage(largeImage, 0, startY, width, height, 0, 0, width, height);
            getMainColorsFromImage(4)
                .then(colors => {
                    let bg = $(".thumbnail-background");
                    bg.css({
                        "background": `linear-gradient(-132deg, ${colors[0]}, ${colors[1]}, ${colors[2]}, ${colors[3]})`,
                        "width": "70%",
                        "padding-bottom": `${largeImage.naturalHeight / largeImage.naturalWidth * 70}%`,
                    });
                    bg.fadeIn(200);
                    $("#largeImage").fadeIn(200);
                })
                .catch(error => { return });

        } catch (e) { }
    }

    img.onload = function () {
        try {
            $("#image").fadeIn(200);
        } catch (e) { }
    }

    function getMainColorsFromImage(numColors) {
        return new Promise((resolve, reject) => {
            const imageData = canvas.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, canvas.width, canvas.height).data;
            const colorCount = {};
            const threshold = 20; // adjust this value to change the threshold for black/white similarity
            const colorGap = 30; // adjust this value to change the minimum color difference between each main color
            for (let i = 0; i < imageData.length; i += 4) {
                const r = imageData[i];
                const g = imageData[i + 1];
                const b = imageData[i + 2];
                const color = `rgb(${r}, ${g}, ${b})`;
                if (!colorCount[color]) {
                    // Check if the color is too close to black or white
                    const isBlackOrWhite = r < threshold || r > 255 - threshold || g < threshold || g > 255 - threshold || b < threshold || b > 255 - threshold;
                    if (isBlackOrWhite) continue;
                    // Check if the color is too similar to previous colors
                    const prevColors = Object.keys(colorCount);
                    const isTooSimilar = prevColors.some(prevColor => {
                        const [pr, pg, pb] = prevColor.match(/\d+/g).map(Number);
                        const diff = Math.sqrt(Math.pow(r - pr, 2) + Math.pow(g - pg, 2) + Math.pow(b - pb, 2));
                        return diff < colorGap;
                    });
                    if (isTooSimilar) continue;
                    colorCount[color] = 0;
                }
                colorCount[color]++;
            }
            const colors = Object.keys(colorCount).sort((color1, color2) => colorCount[color2] - colorCount[color1]).slice(0, numColors);
            resolve(colors);
        });
    }

    $("#seek-bar").on('mousemove', function (e) {
        let position = e.pageX - $(this).offset().left;
        let duration = $(this).width();
        let percentage = (position / duration) * 100;

        let time = player.msToReadableTime(percentage * player.currentTrack?.length / 100);
        $positionInfo.text(time).css({
            left: e.pageX - $positionInfo.outerWidth() / 2,
        });
    });

    $('body').click(function (event) {
        let $target = $(event.target);

        if (!$target.closest(".search-container").length && !$target.is("#search-input") && $('#search-result-list').css("display") != 'none') {
            $("#search-result-list").fadeOut(200);
        }

        else if (!$target.closest(".users-bar").is('.users-bar') &&
            !$target.closest("#users-btn").is('#users-btn') &&
            $(".users-bar").hasClass("active")) {
            $(".users-bar").removeClass("active");
            $("#users-btn").css({ "color": "" });

        } else if ($target.closest(".action").is(".action") &&
            $target.closest(".playlists-tracks").is(".playlists-tracks")) {

            selectedPlaylistTrack = $target.closest(".track").data("value");
            const $contextMenu = $("#context-menu");
            const menuHeight = $contextMenu.outerHeight();
            const windowHeight = $(window).height();
            const topPosition = event.pageY + 30;
            if (topPosition + menuHeight > windowHeight) {
                // If the menu would go out of the page, position it above the btn instead
                $contextMenu.css({ "left": `${event.pageX - 130}px`, "top": `${event.pageY - menuHeight - 30}px` }).fadeIn(200);
            } else {
                $contextMenu.css({ "left": `${event.pageX - 130}px`, "top": `${topPosition}px` }).fadeIn(200);
            }

        } else if ($target.closest(".playlists-tracks").is(".playlists-tracks") &&
            $target.closest(".track").is(".track")) {

            const track_id = $target.closest(".track").data("value");
            player.send({ "op": "addTracks", "tracks": [track_id] })

        } else if ($target.closest(".playlist").is(".playlist")) {
            selectedPlaylistId = $target.closest(".playlist").data("value");

            if ($target.closest(".action").is(".action")) {
                const $contextMenu = $("#playlist-context-menu")

                const menuHeight = $contextMenu.outerHeight();
                const windowHeight = $(window).height();
                const topPosition = event.pageY + 30;
                if (topPosition + menuHeight > windowHeight) {
                    // If the menu would go out of the page, position it above the btn instead
                    $contextMenu.css({ "left": `${event.pageX - 130}px`, "top": `${event.pageY - menuHeight - 30}px` }).fadeIn(200);
                } else {
                    $contextMenu.css({ "left": `${event.pageX - 130}px`, "top": `${topPosition}px` }).fadeIn(200);
                }
            } else if ($target.closest(".play").is(".play")) {
                if (selectedPlaylistId in player.playlists) {
                    if ("tracks" in player.playlists[selectedPlaylistId]) {
                        if (player.playlists[selectedPlaylistId]['tracks'].length != 0) {
                            player.send({ "op": "addTracks", "tracks": player.playlists[selectedPlaylistId]["tracks"] });
                        }
                    }
                }
            } else {
                const $pTracks = $("#playlists-tracks");
                if (selectedPlaylistId in player.playlists) {
                    $pTracks.empty();
                    for (const track_id of player.playlists[selectedPlaylistId]["tracks"]) {
                        const track = decode(track_id);

                        let $trackDiv = $(`<div class="track" data-value=${track_id} ><div class="left">${(this.isDJ) ? '<i class="fa-solid fa-bars handle"></i>' : ''}<img src=${track.imageUrl} /><div class="info"><p>${track.title}</p><p class="desc">${track.author}</p></div></div><p class="time">${player.msToReadableTime(track.length)}</p><i class="fa-solid fa-ellipsis-vertical action"></i></div>`);
                        $pTracks.append($trackDiv);
                    }
                }
            }
        }

        if (!$target.closest(".action").is(".action") &&
            !$target.closest("#context-menu li").is("#context-menu li") &&
            $("#context-menu").css("display") != "none") {
            $("#context-menu").fadeOut(200);
        }

        if (!$target.closest(".action").is(".action") ||
            !$target.closest(".images").is(".images") &&
            $("#playlist-context-menu").css("display") != "none") {
            $("#playlist-context-menu").fadeOut(200);
        }
    });

    $(function () {
        $("#sortable").sortable({
            handle: ".handle",
            scroll: true,
            axis: "y",
            start: function (event, ui) {
                startPos = ui.item.index();
            },
            stop: function (event, ui) {
                if (startPos != null) {
                    let newPos = ui.item.index();
                    if (startPos != newPos) {
                        player.moveTrack(startPos, newPos)
                    }
                }
            }
        });
    });

    $('#sortable').on('click', 'li', function (event) {
        let index = $(this).index();
        let position = player.current_queue_position;

        if ($(event.target).hasClass('action')) {
            selectedTrack = { position: index, track: player.queue[index] };
            const menuHeight = $("#context-menu").outerHeight();
            const windowHeight = $(window).height();
            const topPosition = event.pageY + 30;
            if (topPosition + menuHeight > windowHeight) {
                // If the menu would go out of the page, position it above the btn instead
                $("#context-menu").css({ "left": `${event.pageX - 130}px`, "top": `${event.pageY - menuHeight - 30}px` }).fadeIn(200);
            } else {
                $("#context-menu").css({ "left": `${event.pageX - 130}px`, "top": `${topPosition}px` }).fadeIn(200);
            }
            return;
        }

        if (index < position) {
            player.backTo(position - index);
        } else if (index > position) {
            player.skipTo(index - position)
        } else {
            player.togglePause();
        }
    })

    $('#search-result-list').on('click', 'li', function () {
        let index = $(this).index();
        let track = player.searchList[index];
        if (track != undefined) {
            player.send({ "op": "addTracks", "tracks": [track] });
        }
        $("#search-result-list").fadeOut(200);
    })

    $('#search-input').on('input', function () {
        clearTimeout(typingTimer);
        $("#search-loader").fadeIn(200);
        typingTimer = setTimeout(function () {
            let input = $('#search-input').val();
            if (input.replace(/\s+/g, '') != "") {
                player.send({ "op": "getTracks", "query": input })
            } else {
                $("#search-loader").fadeOut(200);
                $("#search-result-list").fadeOut(200);
            }
        }, doneTypingInterval);
    });

    $('#search-input').focus(function () {
        if ($(this).val() != "") {
            $("#search-result-list").fadeIn(200);
        }
    })

    $('#play-pause-btn').on('click', function () {
        player.togglePause();
    });

    $('#skip-btn').on('click', function () {
        player.skipTo();
    });

    $('#back-btn').on('click', function () {
        player.backTo();
    });

    $('#seek-bar').change(function () {
        player.seekTo($(this).val());
    })

    $("#repeat-btn").on('click', function () {
        player.repeatMode();
    })

    $("#shuffle-btn").on('click', function () {
        player.shuffle();
    })

    $("#users-btn").on('click', function () {
        const userBar = $(".users-bar")
        userBar.toggleClass("active");
        if (userBar.hasClass("active")) {
            $(this).css({ "color": "#fff" });
        } else {
            $(this).css({ "color": "" });
        }

    })

    $("#auto-play").on("click", function () {
        let checkbox = $(this).is(':checked');
        player.send({ "op": "toggleAutoplay", "status": checkbox })
        player.autoplay = checkbox;
    });

    $("#remove-track-btn").on('click', function () {
        if ($("#main").css("display") == "none") {
            if (selectedPlaylistId != null && selectedPlaylistId != null && player.playlists != null) {
                const playlist = player.playlists[selectedPlaylistId];
                if (playlist["type"] == "playlist") {
                    player.send({ "op": "removePlaylistTrack", "pId": selectedPlaylistId, "track_id": selectedPlaylistTrack, "pType": playlist["type"] })
                    let index = playlist["tracks"].indexOf(selectedPlaylistTrack);
                    if (index !== -1) {
                        playlist["tracks"].splice(index, 1);
                    }
                    $(`div [data-value=${selectedPlaylistTrack}]`).remove();
                }
            }
        } else {
            player.removeTrack(selectedTrack?.position, selectedTrack?.track)
        }
        $("#context-menu").fadeOut(200);
    })

    $("#copy-track-btn").on('click', function () {
        if ($("#main").css("display") == "none") {
            if (selectedPlaylistTrack != null) {
                const track = decode(selectedPlaylistTrack);
                navigator.clipboard.writeText(track.uri);
            }
        } else {
            navigator.clipboard.writeText(selectedTrack?.track.uri);
        }
        $("#context-menu").fadeOut(200);
    })

    $("#remove-playlist-btn").on('click', function () {
        if (player.playlists != null && selectedPlaylistId in player.playlists) {
            if (selectedPlaylistId != 200) {
                playlist = player.playlists[selectedPlaylistId];
                console.log(player.playlists);
                let payload = { "op": "removePlaylist", "pId": selectedPlaylistId }
                if (playlist['type'] == "share") {
                    payload["refer_user"] = playlist["user"];
                    payload["isShare"] = true;
                }
                player.send(payload);
                delete player.playlists[selectedPlaylistId];
                player.updatePlaylists();
            }
        }
    })

    $("#homeBtn").on('click', function () {
        $("#playlists").fadeOut(200, function () {
            $("#main").fadeIn(200);
            $(".header").removeClass("active");
        });

    })

    $("#playlistBtn").on('click', function () {
        $("#main").fadeOut(200, function () {
            if (player.playlists == null) {
                player.send({ "op": "getPlaylists" });
            }
            $("#playlists").fadeIn(200);
            $(".header").addClass("active");
        });
    })

    $("#like-btn").on('click', function () {
        let currentTrack = player.currentTrack;
        if (currentTrack != undefined) {
            if (currentTrack.isStream) {
                return player.showToast("error", "You are not allowed to add streaming videos to your playlist!");
            }
            if ($(this).hasClass("fa-regular")) {
                $(this).removeClass("fa-regular").addClass("fa-solid");
                player.send({ "op": "addPlaylistTrack", "track_id": currentTrack.track_id, "pId": "200" })
            } else {
                $(this).removeClass("fa-solid").addClass("fa-regular");
                player.send({ "op": "removePlaylistTrack", "track_id": currentTrack.track_id, "pId": "200" })
            }
        }
    })
});