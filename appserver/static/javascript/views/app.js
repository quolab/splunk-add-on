

import * as Config from "./setup_configuration.js";

const APP_LABEL = "QuoLab Add-on for Splunk";
const APP_NAME = "TA-quolab";
const CONF_TYPE = "Server";
const PATH = "quolab/quolab_servers";
const SECRET_FIELD = "secret";

const confFields = [
    {
    "description": "The server name and port where QuoLab API requests will be sent",
    "display": {
        "class": "input-xlarge"
    },
    "example": "https://example.server.com:1080/service",
    "help": "This is the same URL used for accessing the QuoLab web user interface",
    "label": "URL",
    "name": "url",
    "required": true,
    "type": "url",
    "validation": {
        "type": "regex",
        "value": "^https?://[^\\s]+$"
    }
}
    ,
    {
    "description": "Username for the QuoLab server.",
    "example": "jdoe",
    "help": "Username can be a regular user account name, or 'TOKEN' when using token-based authentication.",
    "label": "Username",
    "name": "username",
    "required": true,
    "type": "string",
    "validation": {
        "type": "regex",
        "value": "^[\\w_.-]+$"
    }
}
    ,
    {
    "default": "HIDDEN",
    "description": "The password associated with the given username or a token",
    "display": {
        "hidden": true
    },
    "label": "Password",
    "name": "secret",
    "required": true,
    "type": "secret"
}
    ,
    {
    "default": true,
    "description": "Use HTTPS certificate validation",
    "help": "The QuoLab HTTPS listener using a publicly signed certificate.  Please understand the security implications of settings this to false.  This should never be false if your QuoLab server is accessed on a public internet connection.",
    "label": "Verify",
    "name": "verify",
    "required": false,
    "type": "bool"
}
    ,
    {
    "default": 500,
    "description": "Number of catalog items to fetch per HTTP call",
    "help": "The maximum number of results that can be fetched in a single query to the API.  If more events are requested at search time then multiple queries will be sent to the API using the supported pagination technique.",
    "label": "Max Batch Size",
    "name": "max_batch_size",
    "required": true,
    "type": "int"
}
    ,
    {
    "default": 300,
    "description": "The longest duration in seconds that any individual query may last.",
    "label": "Max Execution Time",
    "name": "max_execution_time",
    "required": true,
    "type": "int"
}
    ,
    {
    "default": false,
    "description": "Toggle configuration entry status",
    "label": "Disabled",
    "name": "disabled",
    "required": false,
    "type": "bool"
}

];
const confFieldsObject = Object.assign(...confFields.map(key => ({ [key["name"]]: "" })));
const confFieldsArray = Object.keys(confFieldsObject);
const defaultStanzaName = "quolab";
const namespace = { owner: "nobody", app: APP_NAME, sharing: "app" };

const normalizeBoolean = (test) => {
    // Taken from splunkjs SDK (Apache license v2) Copyright 2011 Splunk, Inc.
    if (typeof(test) == 'string') {
        test = test.toLowerCase();
    }

    switch (test) {
        case true:
        case 1:
        case '1':
        case 'yes':
        case 'on':
        case 'true':
            return true;

        case false:
        case 0:
        case '0':
        case 'no':
        case 'off':
        case 'false':
            return false;

        default:
            return test;
    }
};

const resolveSDKError = async (error) => {
    if (typeof(error) == "string" ) return error;

    if (error.responseText) return error.responseText;

    if (error.statusText) return error.statusText;

    if (error.toString() != "[object Object]") {
        return error.toString();
    }

    try {
        return await JSON.stringify(error);
    } catch(error) {
        return "Unable to parse error message.";
    }
};

define(["react", "splunkjs/splunk"], (react, splunkjs) => {
    const ConfEntity = splunkjs.Service.Entity.extend({
        path: () => `${PATH}/${encodeURIComponent(this.name)}`,
        instantiateEntity: (props) => {
            const entityNamespace = splunkjs.Utils.namespaceFromProperties(
                props
            );
            return new splunkjs.Service.Entity(
                this.service,
                props.name,
                entityNamespace
            );
        },
    });

    const ConfCollection = splunkjs.Service.Collection.extend({
        fetchOnEntityCreation: true,
        path: () => PATH,
        instantiateEntity: (props) => {
            const entityNamespace = splunkjs.Utils.namespaceFromProperties(
                props
            );
            return new ConfEntity(this.service, props.name, entityNamespace);
        },
    });

    const update_configuration_data = async (
        splunkjs_service,
        stanza_name,
        properties
    ) => {
        const collection = new ConfCollection(
            splunkjs_service,
            PATH,
            namespace
        );

        const post_response = await collection.post(stanza_name, properties);
        const new_entry = await JSON.parse(post_response);
        return new_entry;
    };

    const perform = async (setupOptions, shouldRunUpdate) => {
        try {
            const http = new splunkjs.SplunkWebHttp();
            const service = new splunkjs.Service(http, namespace);
            const { stanza,  ...properties } = setupOptions;
            await update_configuration_data(service, stanza, properties);

            if (shouldRunUpdate) {
                console.log("Completing setup and reloading app.");
                await Config.completeSetup(service);
                await Config.reloadSplunkApp(service, APP_NAME);
            };
        } catch (error) {
            const resolvedError = await resolveSDKError(error);
            throw new Error(`Submission error: ${resolvedError}`);
        }
    }

    const getConfEntries = async () => {
        try {
            const http = new splunkjs.SplunkWebHttp();
            const service = new splunkjs.Service(http, namespace);

            const collection = new ConfCollection(
                service,
                PATH,
                namespace
            );

            // TODO: change this method to fetch():
            const confEntryJSON = await collection.get("", {});
            const confEntryData = await JSON.parse(confEntryJSON);
            const { entry } = confEntryData;
            entry.forEach( (item) => {
                item.content.disabled = normalizeBoolean(item.content.disabled);
            });

            return entry;
        } catch (error) {
            const resolvedError = await resolveSDKError(error);
            throw new Error(`Error getting configuration entries: ${resolvedError}`);
        }
    }



    const deleteConfEntry = async (name) => {
        try {
            const http = new splunkjs.SplunkWebHttp();
            const service = new splunkjs.Service(http, namespace);

            const entity = new ConfEntity(
                service,
                PATH,
                namespace
            );

            await entity.del(name);
        } catch (error) {
            const resolvedError = await resolveSDKError(error);
            throw new Error(`Error deleting configuration entry: ${resolvedError}`);
        }
    }

    const e = react.createElement;

    const SetupPage = () => {
        const { useEffect, useState } = react;

        const [stanza, setStanza] = useState("");
        const [conf, setConf] = useState(confFieldsObject);
        const [confEntries, setConfEntries] = useState([]);
        const [defaultEntry, setDefaultEntry] = useState([]);
        const [isEditing, setIsEditing] = useState(false);
        const [isFetching, setIsFetching] = useState(true);
        const [showForm, setShowForm] = useState(false);
        const [isFirstRun, setIsFirstRun] = useState(true);
        const [errorMessage, setErrorMessage] = useState(null);

        useEffect(() => {
            const fetchConfEntries = async () => {
                setShowForm(false);

                try {
                    const entries = await getConfEntries();

                    let defaultObject = entries.filter( (entry) => entry.name === "default")[0];
                    defaultObject.content[SECRET_FIELD] = "";

                    const nonDefaults = entries.filter( (entry) => entry.name !== "default");

                    setDefaultEntry(defaultObject);
                    setConfEntries(nonDefaults);
                } catch (error) {
                    console.error(error);
                    setErrorMessage(error.message);
                } finally {
                    setIsFetching(false);
                }

            };

            fetchConfEntries();
        }, [isFetching]);

        const handleChange = (event) => {
            setErrorMessage(null);
            const { name, value } = event.target;

            switch(name) {
                case "stanza":
                    setStanza(value);
                    break;
                default:
                    setConf(prevState => ({
                        ...prevState,
                        [name]: value
                    }));
                }
        };

        const handleCancel= () => {
            setErrorMessage(null);
            setConf(confFieldsObject);
            setIsEditing(false);
            setStanza("");
            setShowForm(!showForm);
        };

        const handleEdit = (event) => {
            setIsEditing(true);
            setShowForm(true);
            setErrorMessage(null);
            const { name } = event.target;
            setStanza(name);
            let conf = confEntries.find(entry => entry.name === name).content;
            setConf(conf);
        };

        const handleNew = () => {
            setShowForm(true);
            setErrorMessage(null);
            setStanza(confEntries.length > 0 ? "" : defaultStanzaName);
            setConf(defaultEntry.content);
        };

        const handleDelete = async (event) => {
            const { name } = event.target;
            await deleteConfEntry(name);
            setIsFetching(true);
        };

        const handleSubmit = async (event) => {
            event.preventDefault();

            try {
                await perform( {stanza, ...conf}, isFirstRun );
                setStanza("");
                setConf(confFieldsObject);
                setIsEditing(false);
                setIsFirstRun(false);
                setShowForm(false);
            } catch (error) {
                setErrorMessage(error.message);
            }

            setIsFetching(true);
        }

        const NewConfEntryButton = () => {
            return e("div", null, [
                    e("div", { class: "pull-right" }, [
                        e("div", { class: "actionButtons" }, [
                            e("a", { href: "#", class: "btn btn-primary", disabled: isFetching, onClick: handleNew }, [
                                e("span", null, `New ${CONF_TYPE}`),
                            ]),
                        ]),
                    ])
            ])
        }

        const ConfEntriesTable = (props) => {
            const { confEntries } = props;

            if (isFetching) return e("h2", null, "Fetching configuration entries...");

            if (!showForm && confEntries.length === 0) return e("h2", null, "No configuration entries found. Add one to get started.");

            return e("div", null, [
                        e("h2", null, "Configuration Entries"),
                        e("table", { class: "table table-striped table-hover" }, [
                            e("thead", null, [
                                e("tr", null, [
                                    e("th", { class: "sorts active" }, "Name"),
                                    confFieldsArray
                                        .filter( (field) => { return field !== SECRET_FIELD } )
                                        .filter( (field) => { return field !== "disabled" } )
                                        .map( (field) => {
                                            return e("th", { class: "sorts" }, `${field[0].toUpperCase() + field.substr(1).toLowerCase()} `)
                                    }),
                                    e("th", { class: "sorts" }, "Actions"),
                                    e("th", { class: "sorts" }, "Status"),
                                ]),
                            ]),
                            e("tbody", null, [
                                confEntries
                                    .filter( (entry) => {
                                        return entry.name !== "default"
                                    })
                                    .map( (entry) => {
                                        return e("tr", null, [
                                            e("td", null, entry.name),
                                            confFieldsArray
                                                .filter( (field) => { return field !== SECRET_FIELD } )
                                                .filter( (field) => { return field !== "disabled" } )
                                                .map( (field) => {
                                                        return e("td", null, entry.content[field])
                                                    }),
                                            e("td", null, [
                                                e("p", null, [
                                                    e("a", { name: entry.name, onClick: handleEdit }, "Edit"),
                                                    e("span", null, " | "),
                                                    e("a", { name: entry.name, onClick: handleDelete }, "Delete")
                                                ]),
                                            ]),
                                            e("td", { class:
                                                `status ${entry.content.disabled ?
                                                "icon-lock disable-icon enable-text" :
                                                "enable-icon icon-check enable-text"}`,
                                                }, entry.content.disabled ? " disabled" : " enabled"),
                                        ])
                                    })
                            ]),
                    ]),
            ]);
        };


        return e("div", null, [
                    e("h2", null, `${APP_LABEL} Setup Page`),
                    showForm ?
                        e("div", { class: "inputForm form-horizontal" }, [
                            e("form", { class: "inputform_wrapper", onSubmit: handleSubmit }, [
                                e("div", { class: "control-group shared-controls-controlgroup control-group-default" }, [
                                    e("div", { class: "controls" }, [
                                        e("div", { class: ""}, [
                                            isEditing ?
                                            e("h3", null, `Editing ${CONF_TYPE} - ${stanza}`)
                                            :
                                            e("div", null, [
                                                e("label", { class: "control-label" }, "Stanza"),
                                                e("input", { type: "text", required: "true", name: "stanza", value: stanza, onChange: handleChange })
                                            ]),
                                        ]),
                                        confFields
                                        .filter( (field) => { return field.name !== "disabled" } )
                                        .map( (field) => {
                                            return e("div", {class:""}, [
                                                        e("label", { class: "control-label" }, field.label),
                                                        e("div", { class: "control input-append shared-controls-textbrowsecontrol control-default"}, [
                                                            e("input", {
                                                                autocomplete: field.type == "secret" ? "off" : "on",
                                                                name: field.name,
                                                                onChange: handleChange,
                                                                placeholder: field.example || "",
                                                                required: field.required,
                                                                type: field.type == "secret" ? "password" : "text",
                                                                value: conf[field.name],
                                                            }),
                                                        ]),
                                                        e("div", { class: "help-block"}, `${field.help || ""}`)
                                                    ])
                                        }),
                                        e("div", null, [
                                            e("a", { href: "#", class: "btn", onClick: handleCancel }, [
                                                e("span", null, "Cancel"),
                                            ]),
                                            e("input", { type: "submit", class: "btn btn-primary", value: "Submit" }),
                                        ]),
                                    ]),
                                ]),
                            ]),
                        ])
                    :
                        e("div", null, [
                            e(NewConfEntryButton, null, null),
                            e(ConfEntriesTable, { confEntries }, null),
                        ]),
                e("div", { class:"alert alert-danger" }, [
                    errorMessage ?
                        e("p", null, errorMessage)
                        :
                        null,
                ]),
        ]);
    };

    return e(SetupPage);
});
