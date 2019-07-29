(function() {


/**
 * An inline editor view for selecting Asana tasks.
 */
const AsanaInlineEditorView = RB.InlineEditorView.extend({
    /**
     * Initialize the view.
     *
     * Args:
     *     options (object):
     *         Options for the view.
     */
    initialize(options) {
        options = _.defaults(options, {
            hasRawValue: true,
            formatResult: value => {
                if (value && value.name) {
                    return value.name.htmlEncode();
                } else {
                    return '';
                }
            },
            getFieldValue: editor => {
                const selectize = this.$field[0].selectize;
                const selected = selectize.getValue();

                return JSON.stringify(selected.map(
                    key => _.pick(
                        selectize.options[key],
                        ['completed', 'gid', 'workspace_id', 'name'])));
            },
            isFieldDirty: (editor, initialValue) => {
                const value = editor.getValue();
                return initialValue !== value;
            },
            setFieldValue: (editor, value) => {
                // This is a no-op, since we do this in the $.selectize call.
            },
        });

        RB.InlineEditorView.prototype.initialize.call(this, options);
    },

    /**
     * Create and return the field to use for the input element.
     *
     * Returns:
     *     jQuery:
     *     The newly created input element.
     */
    createField() {
        return $('<select multiple class="asana-field">');
    },

    /**
     * Connect events.
     */
    setupEvents() {
        RB.InlineEditorView.prototype.setupEvents.call(this);

        this.$field.on('change', this._scheduleUpdateDirtyState.bind(this));
    },

    /**
     * Show the editor.
     *
     * Args:
     *     options (object, optional):
     *         Options for showing the editor.
     */
    showEditor(options={}) {
        RB.InlineEditorView.prototype.showEditor.call(this, options);

        if (this.options.focusOnOpen) {
            this.$field[0].selectize.focus();
        }
    },
});


/**
 * A review request field view for selecting Asana tasks.
 */
RB.ReviewRequestFields.AsanaFieldView =
    RB.ReviewRequestFields.TextFieldView.extend({
    autocomplete: {},
    multiline: true,
    useEditIconOnly: true,

    taskTemplate: _.template(dedent`
        <<%- tagName %> class="asana-task<% if (completed) { %> completed<% } %>">
         <a href="https://app.asana.com/0/<%- workspaceId %>/<%- taskId %>/">
          <div class="asana-task-checkbox">
           <svg viewBox="0 0 32 32">'
            <polygon points="27.672,4.786 10.901,21.557 4.328,14.984 1.5,17.812 10.901,27.214 30.5,7.615"></polygon>
           </svg>
          </div>
          <span><%- taskSummary %></span>
         </a>
        </<%- tagName %>>
        `),

    /**
     * Format the contents of the field.
     *
     * This will apply the contents of the model attribute to the field
     * element. If the field defines a ``formatValue`` method, this will use
     * that to do the formatting. Otherwise, the element will just be set to
     * contain the text of the value.
     */
    _formatField() {
        const fieldName = this.jsonFieldName || this.fieldID;
        const opts = { useExtraData: this.useExtraData };
        const tasks = JSON.parse(this.model.getDraftField(fieldName, opts));
        this._renderValue(tasks);
    },

    /**
     * Render the current value of the field.
     *
     * Args:
     *     tasks (Array of object):
     *         The current value of the field.
     */
    _renderValue(tasks) {
        const lis = tasks.map(task => this.taskTemplate({
            completed: task.completed,
            workspaceId: task.workspace_id,
            taskId: task.gid,
            taskSummary: task.name,
            tagName: 'li',
        }));

        this.$el.html(`<ul>${lis.join('')}</ul>`);
    },

    /**
     * Return the type to use for the inline editor view.
     *
     * Returns:
     *     function:
     *     The constructor for the inline editor class to instantiate.
     */
    _getInlineEditorClass() {
        return AsanaInlineEditorView;
    },

    /**
     * Add auto-complete functionality to the field.
     */
    _buildAutoComplete() {
        const reviewRequest = this.model.get('reviewRequest');
        const localSite = reviewRequest.get('localSitePrefix');
        const reviewRequestId = reviewRequest.get('id');
        const url = `${SITE_ROOT}rbintegrations/asana/${localSite}task-search/${reviewRequestId}/`;
        const $field = this.inlineEditorView.$field;
        const tasks = this.$el.data('raw-value');

        tasks.forEach(task => {
            if (task.gid === undefined) {
                task.gid = String(task.id);
            }
        });

        this._renderValue(tasks || []);

        $field.selectize({
            copyClassesToDropdown: true,
            dropdownParent: 'body',
            labelField: 'name',
            valueField: 'gid',
            multiple: true,
            options: tasks,
            items: tasks.map(task => task.gid),
            optgroupLabelField: 'workspace',
            searchField: 'name',
            sortField: [
                { 'field': 'completed' },
                { 'field': 'name' },
            ],
            render: {
                option: (data, escape) => {
                    return this.taskTemplate({
                        completed: data.completed,
                        workspaceId: data.workspace_id,
                        taskId: data.gid,
                        taskSummary: data.name,
                        tagName: 'div',
                    });
                }
            },
            load(query, callback) {
                const params = $.param({ q: query });

                $.ajax({
                    url: `${url}?${params}`,
                    type: 'GET',
                    error: callback.bind(this),
                    success: res => {
                        const items = [];

                        this.clearOptionGroups();

                        for (let i = 0; i < res.length; i++) {
                            const group = res[i];
                            this.addOptionGroup(group.workspace, group);

                            for (let j = 0; j < group.tasks.length; j++) {
                                const task = group.tasks[j];
                                task.optgroup = group.workspace;
                                task.workspace_id = group.workspace_id;

                                const notesLines = task.notes.split('\n');
                                task.notes = notesLines.splice(8).join('\n');

                                items.push(task);
                            }
                        }

                        this.refreshOptions();
                        callback(items);
                    },
                });
            },
        });
    },
});


})();
