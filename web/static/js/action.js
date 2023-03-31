$(document).ready(function () {
    const player = new Player(userId);
    var startPos = null;
    var selectedTrack = null;

    var typingTimer;
    var doneTypingInterval = 2000;

    $('body').click(function (event) {
        var $target = $(event.target);

        if (!$target.closest(".search-contrainer").is('.search-contrainer') && $('#search-result-list').css("display") != 'none') {
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
