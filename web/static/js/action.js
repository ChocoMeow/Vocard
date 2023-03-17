$(document).ready(function () {
    const player = new Player(userId);
    var startPos = null;

    var typingTimer;
    var doneTypingInterval = 2000;

    $('body').click(function(event) {
        var $target = $(event.target);
        var $resultList = $target.closest(".search-contrainer");

        if (!$resultList.is('.search-contrainer') && $('#search-result-list').css("display") != 'none') {
            $("#search-result-list").fadeOut(200);
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

    $('#sortable').on('click', 'li', function () {
        var index = $(this).index();
        var position = player.current_queue_position;

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

    $("#shuffle-button").on('click', function() {
        player.shuffle();
    })
});