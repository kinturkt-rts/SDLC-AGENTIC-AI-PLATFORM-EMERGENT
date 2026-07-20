/**
 * Server-side Cognito config for the control-plane UI.
 * Pool ID + client ID are public (shipped to the browser); passwords never leave Cognito.
 * Agents / pipeline / backend artifact APIs are not gated by this — UI session only.
 */

export type CognitoPublicConfig = {
  enabled: boolean;
  region: string;
  userPoolId: string;
  userPoolClientId: string;
};

export function getCognitoPublicConfig(): CognitoPublicConfig {
  const userPoolId = (
    process.env.COGNITO_USER_POOL_ID ||
    process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ||
    ''
  ).trim();
  const userPoolClientId = (
    process.env.COGNITO_CLIENT_ID ||
    process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ||
    ''
  ).trim();
  const region = (
    process.env.COGNITO_REGION ||
    process.env.NEXT_PUBLIC_COGNITO_REGION ||
    process.env.AWS_REGION ||
    'us-east-2'
  ).trim();

  const enabled = Boolean(userPoolId && userPoolClientId);

  return {
    enabled,
    region,
    userPoolId,
    userPoolClientId,
  };
}
