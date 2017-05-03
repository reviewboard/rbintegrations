$(function() {
    const $endpoint = $('#id_travis_endpoint');
    const $server = $('#row-travis_custom_endpoint');

    function changeServerVisibility() {
        $server.setVisible($endpoint.val() === 'E');
    }

    $endpoint.change(changeServerVisibility);
    changeServerVisibility();
});
