/**
 * A result from the Asana workspace query URL.
 *
 * Version Added:
 *     4.0.1
 */
interface AsanaWorkspaceResult {
    /** The ID of the workspace. */
    gid: string;

    /** The name of the workspace. */
    name: string;
}


/**
 * The response from the Asana workspace query URL.
 *
 * Version Added:
 *     4.0.1
 */
interface WorkspaceQueryResponse {
    result: string;
    error?: string;
    data?: AsanaWorkspaceResult[];
}


$(function() {
    const $accessToken: JQuery<HTMLInputElement> = $('#id_asana_access_token');
    const $workspace = $('#id_asana_workspace');
    const $error = $('<div class="errorlist">')
        .insertAfter($accessToken)
        .hide();

    $workspace.selectize({
        create: false,
        dropdownParent: 'body',
        searchField: 'name',
        valueField: 'gid',
        labelField: 'name',
        render: {
            option(
                item: AsanaWorkspaceResult,
                escape: (value: string) => string,
            ): string {
                return `<div>${escape(item.name)}</div>`;
            },
        },
        onChange(value: string) {
            $('#id_asana_workspace_name').val(this.options[value].name);
        },
    });

    const selectize = $workspace[0].selectize;
    selectize.$control.width($('#id_name').width());
    selectize.disable();

    function showError(errorStr: string) {
        $error
            .html(dedent`
                <span class="rb-icon rb-icon-warning"></span>
                ${_.escape(errorStr)}
            `)
            .show();
    }

    let lastKey = null;

    const changeWorkspaceEnabled = _.throttle(() => {
        const apiKey = $accessToken.val().trim();

        if (lastKey === apiKey) {
            return;
        }

        lastKey = apiKey;
        $error.hide();
        selectize.disable();

        if (apiKey.length === 0) {
            return;
        }

        selectize.load((callback: (data?: AsanaWorkspaceResult[]) => void) => {
            const params = new URLSearchParams();
            params.append('api_key', apiKey);

            const url = `${SITE_ROOT}rbintegrations/asana/workspaces/`;

            fetch(`${url}?${params.toString()}`)
                .then(rsp => rsp.json())
                .then((rsp: WorkspaceQueryResponse) => {
                    if (rsp.result === 'success') {
                        selectize.enable();
                        callback(rsp.data);
                    } else if (rsp.result === 'error') {
                        showError(rsp.error);
                        callback();
                    } else {
                        console.error(dedent`
                            Unexpected error when fetching Asana workspace list: `,
                            rsp);
                        showError(_`Unable to communicate with Asana`);
                    }
                })
                .catch(err => {
                    console.error(dedent`
                        Unexpected error when fetching Asana workspace list: `,
                        err);
                    showError(_`Unable to communicate with Asana`);
                });
        });
    }, 100);

    $accessToken.on('change keyup', changeWorkspaceEnabled);
    changeWorkspaceEnabled();
});
