$(document).ready(function () {
    const player = new Player(userId);
    const img = document.getElementById("largeImage");
    const canvas = document.createElement('canvas');

    var startPos = null;
    var selectedTrack = null;

    var typingTimer;
    var doneTypingInterval = 2000;

    img.crossOrigin = "Anonymous";
    img.onload = function () {
        try {
            const context = canvas.getContext('2d', {willReadFrequently: true});
            const width = canvas.width = img.width;
            const height = canvas.height = Math.round(img.height * 0.7); // set canvas height to 80% of image height
            const startY = Math.round((img.height - height) / 2); // calculate starting Y coordinate to center the canvas
            context.drawImage(img, 0, startY, width, height, 0, 0, width, height);
            getMainColorsFromImage(4)
            .then(colors => {
                $(".thumbnail-background").css({
                    "background": `linear-gradient(-132deg, ${colors[0]}, ${colors[1]}, ${colors[2]}, ${colors[3]})`,
                    "width": "70%",
                    "padding-bottom": "70%",
                });
            })
            .catch(error => { return });

        } catch(e) {
            
        }
        
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

    $('body').click(function (event) {
        var $target = $(event.target);
        if (!$target.closest(".search-container").length && !$target.is("#search-input") && $('#search-result-list').css("display") != 'none') {
            $("#search-result-list").fadeOut(200);
        }

        if (!$target.closest(".users-bar").is('.users-bar') &&
            !$target.closest("#users-button").is('#users-button') &&
            $(".users-bar").hasClass("active")) {
            $(".users-bar").removeClass("active");
            $("#users-button").css({ "color": "" });
        }

        if (!$target.closest(".action").is(".action") &&
            !$target.closest("#context-menu li").is("#context-menu li") &&
            $("#context-menu").css("display") != "none") {
            $("#context-menu").fadeOut(200);
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
                    var newPos = ui.item.index();
                    if (startPos != newPos) {
                        player.moveTrack(startPos, newPos)
                    }
                }
            }
        });
    });

    $('#sortable').on('click', 'li', function (event) {
        var index = $(this).index();
        var position = player.current_queue_position;

        if ($(event.target).hasClass('action')) {
            selectedTrack = { position: index, track: player.queue[index] };
            $("#context-menu").css({ "left": `${event.pageX - 150}px`, "top": `${event.pageY + 30}px` }).fadeIn(200);
            return
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
        var index = $(this).index();
        var track = player.searchList[index];
        if (track != undefined) {
            player.send({ "op": "addTracks", "tracks": [track] })
        }
        $("#search-result-list").fadeOut(200);
    })

    $('#search-input').on('input', function () {
        clearTimeout(typingTimer);
        $("#search-loader").fadeIn(200);
        typingTimer = setTimeout(function () {
            var input = $('#search-input').val();
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

    $('#play-pause-button').on('click', function () {
        player.togglePause();
    });

    $('#skip-button').on('click', function () {
        player.skipTo();
    });

    $('#back-button').on('click', function () {
        player.backTo();
    });

    $('#seek-bar').change(function () {
        player.seekTo($(this).val());
    })

    $("#repeat-button").on('click', function () {
        player.repeatMode();
    })

    $("#shuffle-button").on('click', function () {
        player.shuffle();
    })

    $("#users-button").on('click', function () {
        const userBar = $(".users-bar")
        userBar.toggleClass("active");
        if (userBar.hasClass("active")) {
            $(this).css({ "color": "#fff" });
        } else {
            $(this).css({ "color": "" });
        }

    })

    $("#remove-track-button").on('click', function () {
        player.removeTrack(selectedTrack?.position, selectedTrack?.track)
        $("#context-menu").fadeOut(200);
    })

    $("#copy-track-button").on('click', function () {
        navigator.clipboard.writeText(selectedTrack?.track.uri);
        $("#context-menu").fadeOut(200);
    })
});
