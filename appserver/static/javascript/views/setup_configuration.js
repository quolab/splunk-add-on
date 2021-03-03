export async function completeSetup(splunkjsService) {
    const apps = splunkjsService.apps();

    const response = await apps.post(splunkjsService.app, {
        configured: "true",
    });

    const update = await JSON.parse(response);

    return update;
}

export async function reloadSplunkApp(splunkjsService, appName) {
    const apps = splunkjsService.apps();
    await apps.fetch();

    const currentApp = apps.item(appName);
    currentApp.reload();
}
