{
  description = "Basic development environment with ffmpeg and ffmpeg-python";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      python = pkgs.python313;
    in {
      devShells.default = pkgs.mkShell {
        buildInputs = [
          pkgs.ffmpeg
          python
        ];
      };
    });
}
