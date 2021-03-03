"use strict";

const APP_NAME = "./TA-quolab";

// This is an undocumented Splunk solution for how to include javascript logic
// from other files.
// Declare a require.config() and provide a dictionary that has a `paths` keys.
// In the `paths` key provide another dictionary that declares custom classes.
// Each key should be the class name, and the value the path to the javascript file
// ../app/<extracted_folder_name_of_app>/<path to javascript file>(no extension)
// Then include those in the require method's array, and function.

// Common gotchas:
// 1) The path to the script automatically appends .js, so don't include it
// 2) This only provides support for JavaScript files, plain-text html files won't work
// 3) The "../app" is required as a prefix and your app name is required to follow it
// 4) After the app name, the path is provided as though it were from the
//    $SPLUNK_HOME/etc/apps/appserver/static/* directory

require.config({
    paths: {
        // $SPLUNK_HOME/etc/apps/SPLUNK_APP_NAME/appserver/static/javascript/views/
        myApp: `../app/${APP_NAME}/javascript/views/app`,
        react: `../app/${APP_NAME}/javascript/vendor/react.production.min`,
        ReactDOM: `../app/${APP_NAME}/javascript/vendor/react-dom.production.min`,
    },
    scriptType: "module",
});

require([
    // Splunk Web Framework Provided files
    // Custom files
    "react", // this needs to be lowercase because ReactDOM refers to it as lowercase
    "ReactDOM",
    "myApp",
], function (react, ReactDOM, myApp) {
    ReactDOM.render(myApp, document.getElementById("main_container"));
});
