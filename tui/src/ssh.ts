import {Client} from 'ssh2';
import {lookup} from 'node:dns/promises';

export type SshConfig = {
	host: string;
	port: number;
	username: string;
	password: string;
};

export type PumpStatus = {
	connected?: boolean;
	controller_mode?: string;
	current_amps?: number | null;
	decision?: {
		action?: string | null;
		reason?: string | null;
		state?: string | null;
		ts?: string | null;
	};
	host?: string;
	last_lora_ts?: string | null;
	lora_age_s?: number | null;
	lora_pkt?: number | null;
	lora_rssi?: number | null;
	lora_snr?: number | null;
	ml_prediction?: {
		start_hour?: number;
		duration?: number;
	} | null;
	override?: string | null;
	pressure_kpa?: number | null;
	pump_relay_on?: boolean;
	sensor_status?: string | null;
	sensor_voltage?: number | null;
	status_file?: string;
	timestamp?: string;
	upper_pct?: number | null;
	voltage_ac?: number | null;
	error?: string;
};

const REMOTE_ROOT = '/home/wilopi/Desktop/Wilo-Water-Pump-Automation';
const REMOTE_BRIDGE = `${REMOTE_ROOT}/src/controller/remote_bridge.py`;

const resolveHost = async (host: string): Promise<string> => {
	try {
		const resolved = await lookup(host, {family: 4});
		return resolved.address;
	} catch {
		return host;
	}
};

const runCommand = async (config: SshConfig, command: string): Promise<string> =>
	new Promise((resolve, reject) => {
		const client = new Client();
		let stdout = '';
		let stderr = '';

		void resolveHost(config.host)
			.then(resolvedHost => {
				client
					.on('ready', () => {
						client.exec(command, (error, stream) => {
							if (error) {
								client.end();
								reject(error);
								return;
							}

							stream
								.on('close', (code: number | null) => {
									client.end();
									if (code && code !== 0) {
										reject(new Error(stderr.trim() || `Remote command exited with code ${code}`));
										return;
									}

									resolve(stdout.trim());
								})
								.on('data', (chunk: Buffer) => {
									stdout += chunk.toString();
								});

							stream.stderr.on('data', (chunk: Buffer) => {
								stderr += chunk.toString();
							});
						});
					})
					.on('error', error => {
						reject(error);
					})
					.connect({
						host: resolvedHost,
						password: config.password,
						port: config.port,
						readyTimeout: 10000,
						username: config.username,
					});
			})
			.catch(reject);
	});

export const fetchStatus = async (config: SshConfig): Promise<PumpStatus> => {
	const raw = await runCommand(config, `python3 ${REMOTE_BRIDGE} status`);
	return JSON.parse(raw) as PumpStatus;
};

export const setOverride = async (config: SshConfig, mode: 'on' | 'off' | 'clear'): Promise<void> => {
	await runCommand(config, `python3 ${REMOTE_BRIDGE} override ${mode}`);
};

export const setPumpState = async (config: SshConfig, mode: 'on' | 'off'): Promise<void> => {
	await runCommand(config, `python3 ${REMOTE_BRIDGE} pump ${mode}`);
};
