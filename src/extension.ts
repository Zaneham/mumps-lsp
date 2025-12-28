import * as path from 'path';
import * as vscode from 'vscode';
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind
} from 'vscode-languageclient/node';

let client: LanguageClient;

export function activate(context: vscode.ExtensionContext) {
    // Get configuration - because even healthcare IT needs settings
    const config = vscode.workspace.getConfiguration('mumps');
    const pythonPath = config.get<string>('pythonPath', 'python');
    const customServerPath = config.get<string>('serverPath', '');

    // Determine server path - bundled or custom (for the adventurous)
    const serverScript = customServerPath ||
        path.join(context.extensionPath, 'server', 'mumps_server.py');

    // Server options - spawning the Python process
    // Much like spawning a healthcare billing query, but faster
    const serverOptions: ServerOptions = {
        command: pythonPath,
        args: [serverScript],
        transport: TransportKind.stdio
    };

    // Client options - what we're actually working with
    const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: 'file', language: 'mumps' }],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher('**/*.{m,mps,mumps,ros,int}')
        },
        outputChannelName: 'MUMPS Language Server'
    };

    // Create and start the language client
    // Your medical records are in safe hands. Probably.
    client = new LanguageClient(
        'mumpsLanguageServer',
        'MUMPS Language Server',
        serverOptions,
        clientOptions
    );

    // Start the client - this also launches the server
    client.start();

    // Register a command to show MUMPS info
    const showInfoCommand = vscode.commands.registerCommand('mumps.showInfo', () => {
        vscode.window.showInformationMessage(
            'MUMPS/M: Powering healthcare since 1966. ' +
            'Your medical records are stored in a language older than most doctors.'
        );
    });

    context.subscriptions.push(showInfoCommand);
}

export function deactivate(): Thenable<void> | undefined {
    if (!client) {
        return undefined;
    }
    return client.stop();
}
