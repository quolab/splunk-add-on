

import * as Config from "./setup_configuration.js";

const APP_LABEL = "QuoLab Add-on for Splunk";
const APP_NAME = "TA-quolab";
const CONF_TYPE = "Server";
const PATH = "quolab/quolab_servers";
const SECRET_NAME = "secret";

const confFieldsArray = [
    "url",
    "username",
    "max_batch_size",
    "max_execution_time",
    "verify"
].concat(SECRET_NAME);
const confFieldsObject = Object.assign(...confFieldsArray.map(key => ({ [key]: "" })));
const defaultStanzaName = "quolab";
const namespace = { owner: "nobody", app: APP_NAME, sharing: "app" };

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

            // eventually remove this:
            const sanitizedEntries = entry.map((item) => {
                delete item.content[SECRET_NAME];
                return item;
             });

            return sanitizedEntries;
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
                    defaultObject.content[SECRET_NAME] == "";
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
            delete conf[SECRET_NAME];
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
                                        .filter( (field) => { return field !== SECRET_NAME } )
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
                                                .filter( (field) => { return field !== SECRET_NAME } )
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
                        e("div", null, [
                            e("form", { onSubmit: handleSubmit }, [
                                e("div", null, [
                                    isEditing ?
                                    e("h3", null, `Editing ${CONF_TYPE} - ${stanza}`)
                                    :
                                    e("label", null, [
                                        "Stanza: ",
                                        e("input", { type: "text", required: "true", name: "stanza", value: stanza, onChange: handleChange })
                                    ]),
                                ]),
                                confFieldsArray.map( (field) => {
                                    return e("label", null, [
                                            `${field[0].toUpperCase() + field.substr(1).toLowerCase()}: `,
                                                e("input", {
                                                    type: field === SECRET_NAME ? "password" : "text",
                                                    name: field,
                                                    value: conf[field],
                                                    autocomplete: field === SECRET_NAME ? "off" : "on",
                                                    onChange: handleChange
                                                    }
                                                )
                                            ])
                                }),
                                e("div", null, [
                                    e("a", { href: "#", class: "btn", onClick: handleCancel }, [
                                        e("span", null, "Cancel"),
                                    ]),
                                    e("input", { type: "submit", class: "btn btn-primary", value: "Submit" }),
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
