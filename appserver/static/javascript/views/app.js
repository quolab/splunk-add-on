/**
 */

import * as Config from "./setup_configuration.js";

const appLabel = "QuoLab add-on for Splunk";
const confFieldsArray = [
    "url",
    "username",
    "max_batch_size",
    "max_execution_time",
    "verify",
].concat("secret");
const confFieldsObject = Object.assign(
    ...confFieldsArray.map((key) => ({ [key]: "" }))
);

const APP_NAME = "TA-quolab";
const PATH = "quolab_servers/quolab_serversendpoint";

const namespace = {
    owner: "nobody",
    app: APP_NAME,
    sharing: "app",
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

    const perform = async (setupOptions, runUpdate) => {
        try {
            const http = new splunkjs.SplunkWebHttp();
            const service = new splunkjs.Service(http, namespace);
            const { stanza, confs, ...properties } = setupOptions;

            await update_configuration_data(service, stanza, properties);

            if (runUpdate || true) {
                await Config.completeSetup(service);
                await Config.reloadSplunkApp(service, APP_NAME);
            }
        } catch (error) {
            console.error(error);
        }
    };

    const getConfEntries = async () => {
        try {
            const http = new splunkjs.SplunkWebHttp();
            const service = new splunkjs.Service(http, namespace);

            const collection = new ConfCollection(service, PATH, namespace);

            // TODO: change this method to fetch()
            const conf_entry_JSON = await collection.get("", {});
            const conf_entry_data = await JSON.parse(conf_entry_JSON);
            const { entry } = conf_entry_data;

            const sanitized_entries = entry.map((item) => {
                item.content.secret = "[masked]";
                return item;
            });

            return sanitized_entries;
        } catch (error) {
            console.error(error);
        }
    };

    const e = react.createElement;

    const SetupPage = () => {
        const [stanza, setStanza] = react.useState("");
        const [conf, setConf] = react.useState(confFieldsObject);
        const [confEntries, setConfEntries] = react.useState([]);
        const [isError, setIsError] = react.useState(false);
        const [isFetching, setIsFetching] = react.useState(true);
        const [showTable, setShowTable] = react.useState(false);
        const [showForm, setShowForm] = react.useState(false);
        const [isFirstRunComplete, setFirstRunComplete] = react.useState(false);

        react.useEffect(() => {
            const fetchConfEntries = async () => {
                setIsError(false);

                try {
                    const entries = await getConfEntries();
                    if (entries.length > 0) setFirstRunComplete(true);
                    setConfEntries(entries);
                    setShowTable(true);
                } catch (error) {
                    setIsError(true);
                    setIsFetching(false);
                    setShowTable(false);
                    console.error(error);
                }

                setIsFetching(false);
            };

            fetchConfEntries();
        }, [isFetching]);

        const handleChange = (event) => {
            setIsError(false);
            const { name, value } = event.target;

            switch (name) {
                case "stanza":
                    setStanza(value);
                    break;
                default:
                    setConf((prevState) => ({
                        ...prevState,
                        [name]: value,
                    }));
            }
        };

        const handleEdit = (event) => {
            const { name } = event.target;
            setStanza(name);
            const { url, username, token, verify } = confEntries.find(
                (entry) => entry.name === name
            ).content;
            setConf({ url, username, token, verify });
            setShowForm(true);
            setShowTable(false);
        };

        const handleSubmit = async (event) => {
            event.preventDefault();

            try {
                await perform({ stanza, ...conf }, isFirstRunComplete);
                setStanza("");
                setConf(confFieldsObject);
                setShowForm(false);
                setShowTable(true);
            } catch (error) {
                console.error(error);
            }

            setIsFetching(true);
        };

        const toggleForm = () => {
            setStanza("");
            setConf(confFieldsObject);
            setShowForm(!showForm);
            setShowTable(!showTable);
        };

        const NewConfEntryButton = () => {
            return e("div", null, [
                e("div", { class: "pull-right" }, [
                    e("div", { class: "actionButtons" }, [
                        e(
                            "a",
                            {
                                href: "#",
                                class: "btn-primary",
                                onClick: toggleForm,
                            },
                            [e("span", null, "New Entry")]
                        ),
                    ]),
                ]),
            ]);
        };

        const ConfEntriesTable = (props) => {
            const { confEntries } = props;

            if (confEntries === [])
                return e(
                    "h2",
                    null,
                    "Add a configuration entry to get started."
                );

            return e("div", null, [
                e("h2", null, "Configuration Entries"),
                e("table", { class: "table table-striped table-hover" }, [
                    e("thead", null, [
                        e("tr", null, [
                            e("th", { class: "sorts active" }, "Name"),
                            confFieldsArray.map((field) => {
                                return e(
                                    "th",
                                    { class: "sorts" },
                                    `${
                                        field[0].toUpperCase() +
                                        field.substr(1).toLowerCase()
                                    }: `
                                );
                            }),
                            e("th", { class: "sorts" }, "Actions"),
                            e("th", { class: "sorts" }, "Status"),
                        ]),
                    ]),
                    e("tbody", null, [
                        confEntries.map((entry) => {
                            return e("tr", null, [
                                e("td", null, entry.name),
                                confFieldsArray.map((field) => {
                                    return e("td", null, entry.content[field]);
                                }),
                                e("td", null, [
                                    e(
                                        "a",
                                        {
                                            name: entry.name,
                                            onClick: handleEdit,
                                        },
                                        "Edit"
                                    ),
                                ]),
                                e(
                                    "td",
                                    {
                                        class: `status ${
                                            entry.content.disabled
                                                ? "icon-lock disable-icon enable-text"
                                                : "enable-icon icon-check enable-text"
                                        }`,
                                    },
                                    entry.content.disabled
                                        ? "disabled"
                                        : "enabled"
                                ),
                            ]);
                        }),
                    ]),
                ]),
            ]);
        };

        return e("div", null, [
            e("h2", null, `${appLabel} Setup Page`),
            !showForm ? e(NewConfEntryButton, null, null) : null,
            showForm
                ? e("div", { class: "setup container" }, [
                      e("form", { class: "right", onSubmit: handleSubmit }, [
                          e("div", null, [
                              e("label", null, [
                                  "Stanza: ",
                                  e("input", {
                                      type: "text",
                                      name: "stanza",
                                      value: stanza,
                                      onChange: handleChange,
                                  }),
                              ]),
                          ]),
                          confFieldsArray.map((field) => {
                              return e("label", null, [
                                  `${
                                      field[0].toUpperCase() +
                                      field.substr(1).toLowerCase()
                                  }: `,
                                  e("input", {
                                      type: "text",
                                      name: field,
                                      value: conf[field],
                                      onChange: handleChange,
                                  }),
                              ]);
                          }),
                          e(
                              "a",
                              { href: "#", class: "btn", onClick: toggleForm },
                              [e("span", null, "Cancel")]
                          ),
                          e("input", {
                              type: "submit",
                              class: "btn-primary",
                              value: "Submit",
                          }),
                      ]),
                  ])
                : null,
            showTable ? e(ConfEntriesTable, { confEntries }, null) : null,
            isError
                ? e("p", null, "Error fetching configuration entries.")
                : null,
        ]);
    };

    return e(SetupPage);
});
