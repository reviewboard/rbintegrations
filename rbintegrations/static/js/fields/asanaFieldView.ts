/**
 * A review request field view for selecting Asana tasks.
 */

import { spina } from '@beanbag/spina';
import { ReviewRequestFields } from 'reviewboard/reviews';
import { InlineEditorView } from 'reviewboard/ui';
import {
    type InlineEditorViewOptions,
} from 'reviewboard/ui/views/inlineEditorView';


/**
 * An inline editor view for selecting Asana tasks.
 */
@spina
class AsanaInlineEditorView extends InlineEditorView {
    /**
     * Initialize the view.
     *
     * Args:
     *     options (object):
     *         Options for the view.
     */
    initialize(options: Partial<InlineEditorViewOptions>) {
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

        super.initialize(options);
    }

    /**
     * Create and return the field to use for the input element.
     *
     * Returns:
     *     jQuery:
     *     The newly created input element.
     */
    createField() {
        return $('<select multiple class="asana-field">');
    }

    /**
     * Connect events.
     */
    setupEvents() {
        super.setupEvents();

        this.$field.on('change', this._scheduleUpdateDirtyState.bind(this));
    }

    /**
     * Show the editor.
     *
     * Args:
     *     options (object, optional):
     *         Options for showing the editor.
     */
    showEditor(options={}) {
        super.showEditor(options);

        if (this.options.focusOnOpen) {
            this.$field[0].selectize.focus();
        }
    }
}


/**
 * A task entry in the selector.
 *
 * Version Added:
 *     4.0.1
 */
interface TaskEntry {
    /** Whether the task is completed. */
    completed: boolean;

    /** The ID of the workspace that the task is in. */
    workspace_id: string;

    /** The ID of the task. */
    gid: string;

    /** Alternate ID field for the task. */
    id?: string;

    /** The option group ID. */
    optgroup?: string;

    /** The summary of the task. */
    name: string;

    /** The description of the task. */
    notes: string;
}


/**
 * The response from the Asana task query URL.
 *
 * Version Added:
 *     4.0.1
 */
interface TaskQueryResponse {
    workspace: string;
    workspace_id: string;
    tasks: TaskEntry[];
}


/**
 * A review request field view for selecting Asana tasks.
 */
@spina({
    prototypeAttrs: ['taskTemplate'],
})
export class AsanaFieldView extends ReviewRequestFields.TextFieldView {
    static autocomplete = {};
    static multiline = true;
    static useEditIconOnly = true;

    static taskTemplate = _.template(dedent`
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
    `);
    taskTemplate: _.CompiledTemplate;

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
    }

    /**
     * Render the current value of the field.
     *
     * Args:
     *     tasks (Array of object):
     *         The current value of the field.
     */
    _renderValue(tasks: TaskEntry[]) {
        const lis = tasks.map(task => this.taskTemplate({
            completed: task.completed,
            workspaceId: task.workspace_id,
            taskId: task.gid,
            taskSummary: task.name,
            tagName: 'li',
        }));

        this.$el.html(`<ul>${lis.join('')}</ul>`);
    }

    /**
     * Return the type to use for the inline editor view.
     *
     * Returns:
     *     function:
     *     The constructor for the inline editor class to instantiate.
     */
    _getInlineEditorClass(): typeof InlineEditorView {
        return AsanaInlineEditorView;
    }

    /**
     * Add auto-complete functionality to the field.
     */
    _buildAutoComplete() {
        const reviewRequest = this.model.get('reviewRequest');
        const localSite = reviewRequest.get('localSitePrefix');
        const reviewRequestId = reviewRequest.get('id');
        const url = `${SITE_ROOT}rbintegrations/asana/${localSite}task-search/${reviewRequestId}/`;
        const $field = this.inlineEditorView.$field;
        const tasks = this.$el.data('raw-value') || [];

        tasks.forEach((task: TaskEntry) => {
            if (task.gid === undefined) {
                task.gid = String(task.id);
            }
        });

        this._renderValue(tasks);

        $field.selectize({
            copyClassesToDropdown: true,
            dropdownParent: 'body',
            labelField: 'name',
            valueField: 'gid',
            multiple: true,
            options: tasks,
            items: tasks.map((task: TaskEntry) => task.gid),
            optgroupLabelField: 'workspace',
            searchField: 'name',
            sortField: [
                { 'field': 'completed' },
                { 'field': 'name' },
            ],
            render: {
                option: (data: TaskEntry) => {
                    return this.taskTemplate({
                        completed: data.completed,
                        workspaceId: data.workspace_id,
                        taskId: data.gid,
                        taskSummary: data.name,
                        tagName: 'div',
                    });
                }
            },
            load(
                query: string,
                callback: (data?: TaskEntry[]) => void,
            ) {
                const params = new URLSearchParams();
                params.append('q', query);

                fetch(`${url}?${params.toString()}`)
                    .then(rsp => rsp.json())
                    .then((rsp: TaskQueryResponse[]) => {
                        const items: TaskEntry[] = [];
                        this.clearOptionGroups();

                        for (const group of rsp) {
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
                    })
                    .catch(err => {
                        console.error('Unable to fetch Asana tasks:', err);
                        callback();
                    });
            },
        });
    }
}
